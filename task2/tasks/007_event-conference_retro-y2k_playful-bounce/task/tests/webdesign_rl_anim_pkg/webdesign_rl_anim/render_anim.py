"""Deterministic *filmstrip* render of an animated HTML page via Chromium.

Task 1 renders one full-page screenshot per page after ``networkidle`` with
``reduced_motion="reduce"`` — i.e. it deliberately *freezes* animation to get a
single deterministic still. Task 2 needs the opposite: a reproducible sequence
of frames *through* the animation. Sleeping for N ms and screenshotting is not
reproducible (frame timing drifts with CPU speed/load), so instead we **seek the
animation timeline**: pause every running animation and set its ``currentTime``
to a fixed absolute offset via the Web Animations API, then screenshot. The same
``(page, t)`` produces byte-identical pixels on any machine.

This is why the generated reference is constrained to **declarative, timeline-
seekable CSS animations** (``@keyframes`` + transitions): ``document.getAnimations()``
exposes exactly those, and their ``currentTime`` is settable. ``requestAnimationFrame``
JS loops are intentionally out of scope for v1 — they are not seekable this way.

The local-server + offline-network + deterministic-Chromium-flags machinery is
copied from Task 1's ``render/browser.py`` (kept independent so Task 1 is never
touched); the new part is :func:`render_filmstrip`.
"""

import functools
import http.server
import io
import socketserver
import threading
from contextlib import contextmanager
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

# Chromium launch flags for run-to-run determinism (identical to Task 1).
_LAUNCH_ARGS = [
    "--disable-gpu",
    "--force-color-profile=srgb",
    "--disable-lcd-text",
    "--hide-scrollbars",
]

# Default filmstrip sample points (ms, absolute on the document timeline). Chosen
# to straddle a typical entrance (0-800ms), a stagger tail (~1000ms), and at least
# one cycle of a ~1600ms loop. The grader seeks BOTH reference and candidate to
# these same absolute times, so a candidate with the wrong duration/easing renders
# different pixels here and is penalised automatically.
DEFAULT_TIMESTAMPS_MS = (0, 200, 500, 900, 1400, 2000)

# "Settled" frame: seek far past every finite animation's end so the page is at
# rest (fill-mode forwards holds the end state). Used for the static 4-term, which
# should grade the final design, not a mid-transition frame.
SETTLED_MS = 100_000

# After seeking, wait two animation frames so the compositor paints the new
# (paused) state before we screenshot. rAF still fires — only the animations are
# paused — so this is a bounded, deterministic wait, not a wall-clock sleep.
_PAINT_WAIT_JS = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"

# Pause every running animation and pin it to absolute time ``t`` (ms). Returns
# the count so callers can detect a page that declares no animations at all.
_SEEK_JS = """
(t) => {
  const anims = document.getAnimations();
  for (const a of anims) {
    try { a.pause(); a.currentTime = t; } catch (e) { /* unseekable; skip */ }
  }
  return anims.length;
}
"""

# The SETTLED frame should show the *resting design*, which the static terms grade.
# Finite (entrance/stagger) animations are seeked to their end (fill-mode forwards
# holds it); INFINITE loops never rest, so pin them to a canonical phase
# (currentTime 0) instead of an arbitrary ``t % duration`` snapshot. This makes the
# settled frame independent of loop timing — so the static design score doesn't
# move when only the animation timing differs (between a candidate and the
# reference, or across the perturbation ladder).
_SETTLED_SEEK_JS = """
(t) => {
  const anims = document.getAnimations();
  for (const a of anims) {
    try {
      a.pause();
      let iters = Infinity;
      try { iters = a.effect.getComputedTiming().iterations; } catch (e) {}
      a.currentTime = isFinite(iters) ? t : 0;
    } catch (e) { /* unseekable; skip */ }
  }
  return anims.length;
}
"""


@contextmanager
def _serve(site_dir: Path):
    """Serve ``site_dir`` over HTTP on an ephemeral localhost port (see Task 1)."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(site_dir)
    )

    class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = _Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()


def render_filmstrip(
    site_dir,
    html_file,
    timestamps_ms=DEFAULT_TIMESTAMPS_MS,
    *,
    viewport: int = 1280,
    settled_ms: int = SETTLED_MS,
):
    """Render one animated page to a deterministic filmstrip + a settled frame.

    Args:
        site_dir: directory of HTML/CSS/assets to serve and render.
        html_file: the page to load (relative to ``site_dir``).
        timestamps_ms: absolute document-timeline offsets to capture, in order.
        viewport: capture width in CSS px (full scroll height).
        settled_ms: time to seek for the at-rest frame used by the static terms.

    Returns:
        ``{"frames": [PIL.Image, ...], "timestamps_ms": [...],
           "settled": PIL.Image, "n_animations": int}`` — ``frames`` aligned to
        ``timestamps_ms``; ``n_animations`` is the count of declared animations
        (0 ⇒ the page is static, which the motion term scores at the floor).
    """
    site_dir = Path(site_dir)
    timestamps = list(timestamps_ms)

    with _serve(site_dir) as base_url, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        try:
            context = browser.new_context(
                viewport={"width": viewport, "height": 720},
                device_scale_factor=1,
                # NOT reduced-motion: we WANT the animations, then seek them.
                reduced_motion="no-preference",
            )
            page = context.new_page()
            # Offline determinism: serve from our local server, abort everything
            # external (fonts/assets/analytics) so the page renders promptly.
            page.route(
                "**/*",
                lambda route: (
                    route.continue_()
                    if route.request.url.startswith(base_url)
                    else route.abort()
                ),
            )
            page.goto(f"{base_url}/{html_file}", wait_until="networkidle")

            n_anim = 0
            frames = []
            for t in timestamps:
                count = page.evaluate(_SEEK_JS, t)
                n_anim = max(n_anim, count)
                page.evaluate(_PAINT_WAIT_JS)
                frames.append(_shoot(page))

            page.evaluate(_SETTLED_SEEK_JS, settled_ms)
            page.evaluate(_PAINT_WAIT_JS)
            settled = _shoot(page)
        finally:
            browser.close()

    return {
        "frames": frames,
        "timestamps_ms": timestamps,
        "settled": settled,
        "n_animations": n_anim,
    }


def _shoot(page) -> Image.Image:
    """Full-page screenshot of the current (paused) state as a PIL RGB image."""
    png = page.screenshot(full_page=True, type="png")
    return Image.open(io.BytesIO(png)).convert("RGB")
