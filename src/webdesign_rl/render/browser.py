"""Render a directory of HTML/CSS to deterministic screenshots via Chromium.

``render_site`` is a deep module behind a small interface: hand it a site
directory and a ``page_map`` and it returns one full-page :class:`PIL.Image` per
page, captured offline at a fixed width. All of the orchestration the grader
must not care about — spinning up a local HTTP server, launching headless
Chromium with deterministic flags, blocking the network, and stitching a
full-page screenshot — lives behind that one call.

**Why a local HTTP server, not ``file://``:** served over ``http://localhost``,
relative asset paths (``logo.png``) and ``@font-face`` ``src`` URLs resolve the
same way they do in a real browser; ``file://`` breaks many of those and changes
CORS/font behavior, so the grader would score something the agent never sees.

**Offline determinism.** Every request whose host is not the local server is
aborted via route interception, so no external webfont/asset/analytics request
can load or even be awaited — the page still renders, it just renders without the
blocked resource. Combined with the deterministic Chromium flags (headless,
disabled GPU, fixed device-scale-factor of 1, reduced motion / disabled
animations, sRGB color profile) the same site renders the same way every run,
independent of the network.

**Fonts.** For this spike, determinism comes from blocking external webfonts and
relying only on locally-available fonts (the fixture's ``@font-face`` falls back
to a system sans-serif). For cross-environment reproducibility (e.g. the Harbor
verifier image) a fixed font set would be *bundled into the image and referenced
by a relative ``@font-face`` ``src`` served over this same HTTP server* — no code
change here, just shipping the .woff2/.ttf files alongside the site and pointing
``src`` at them. We deliberately do not depend on the network for fonts.
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

# Chromium launch flags chosen for run-to-run determinism: no GPU/threaded
# raster variance, fixed sRGB color handling.
_LAUNCH_ARGS = [
    "--disable-gpu",
    "--force-color-profile=srgb",
    "--disable-lcd-text",
    "--hide-scrollbars",
]


@contextmanager
def _serve(site_dir: Path):
    """Serve ``site_dir`` over HTTP on an ephemeral localhost port.

    Yields the base URL (``http://127.0.0.1:<port>``). The server runs in a
    daemon thread and is shut down on exit, so nothing leaks between renders.
    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(site_dir)
    )

    # ThreadingHTTPServer + port 0 -> the OS picks a free ephemeral port.
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


def render_site(site_dir, page_map, viewport: int = 1280):
    """Render each page of ``site_dir`` to a full-page screenshot.

    Args:
        site_dir: directory of HTML/CSS/asset files to serve and render.
        page_map: ``{page: {"expected_file": "<name>.html", ...}}`` — each page's
            ``expected_file`` is the HTML file (relative to ``site_dir``) to load.
        viewport: capture width in CSS pixels (default 1280). Height is the full
            scroll height of the page.

    Returns:
        ``{page: PIL.Image}`` — one full-page RGB screenshot per page whose HTML
        file exists. A page whose ``expected_file`` is absent is omitted from the
        result (the grader treats an absent page as a zero score).
    """
    site_dir = Path(site_dir)

    images = {}
    with _serve(site_dir) as base_url, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        try:
            for page_name, spec in page_map.items():
                html_file = spec["expected_file"]
                if not (site_dir / html_file).exists():
                    continue
                images[page_name] = _capture(
                    browser, base_url, html_file, viewport
                )
        finally:
            browser.close()
    return images


def _capture(browser, base_url, html_file, viewport):
    """Capture one full-page screenshot of ``html_file`` as a PIL image."""
    context = browser.new_context(
        viewport={"width": viewport, "height": 720},
        device_scale_factor=1,
        reduced_motion="reduce",
    )
    page = context.new_page()
    try:
        # Offline determinism: serve anything on our local server, abort
        # everything else (external fonts/assets/analytics). Aborting — not
        # fulfilling/awaiting — means a page that references an unreachable
        # external host still renders promptly without it.
        page.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(base_url)
                else route.abort()
            ),
        )
        page.goto(f"{base_url}/{html_file}", wait_until="networkidle")
        png = page.screenshot(full_page=True, type="png")
    finally:
        context.close()
    return Image.open(io.BytesIO(png)).convert("RGB")
