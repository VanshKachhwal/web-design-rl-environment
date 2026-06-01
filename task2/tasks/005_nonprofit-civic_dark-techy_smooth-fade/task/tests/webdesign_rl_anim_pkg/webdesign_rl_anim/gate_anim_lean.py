"""The lean, render-based quality gate for animated sites (throughput-first).

Per the scaling decision we check only the *necessary* things — the structural/
token/manifest battery from Task 1 is dropped. A site passes iff, for every page:

1. **completeness** — the page's HTML exists, and the shared stylesheets exist.
2. **no JS** — no ``<script>`` anywhere (JS motion is invisible to the timeline-seek
   grader, so a JS site is ungradeable).
3. **renders + animates** — the filmstrip renderer (offline) reports ``n_animations > 0``,
   the frames actually **vary over time** (motion is present, not a static page), and
   the settled frame is **non-blank**. Rendering offline also implicitly covers
   hermeticity: if it renders with motion under a blocked network, external-resource
   hygiene is moot.

Diagnostics are ``{check, page, message}`` dicts (like Task 1's gate) so the
orchestrator can report *why* a site dropped.
"""

import numpy as np
from PIL import Image

# Motion / blank thresholds on a coarse luminance grid in [0,1]. Lenient by design.
# Motion uses the MAX per-cell change between consecutive frames, not the grid mean:
# localized motion on a sparse page (small content over a big background) is real
# animation but averages to ~0, so a mean test would wrongly reject it.
_MOTION_EPS = 0.03     # a single grid cell changing this much ⇒ "moving"
_BLANK_STD = 0.015     # settled-frame luminance std below this ⇒ effectively blank
_GRID = (16, 12)


def _gray_grid(img: Image.Image):
    return np.asarray(img.convert("L").resize(_GRID, Image.BILINEAR), np.float32) / 255.0


def _frames_vary(frames) -> bool:
    arrs = [_gray_grid(f) for f in frames]
    return any(
        float(np.abs(arrs[i + 1] - arrs[i]).max()) > _MOTION_EPS
        for i in range(len(arrs) - 1)
    )


def _is_blank(img: Image.Image) -> bool:
    return float(_gray_grid(img).std()) < _BLANK_STD


def _diag(check, page, message):
    return {"check": check, "page": page, "message": message}


def run_lean_gate(site_dir, plan, render_filmstrip) -> list:
    """Return a list of failure diagnostics for ``site_dir`` (empty list = passed).

    ``render_filmstrip(site_dir, html_file)`` must return the filmstrip dict
    (``frames`` / ``settled`` / ``n_animations``) — injected so this stays testable.
    """
    from pathlib import Path
    site_dir = Path(site_dir)
    diags = []

    for shared in ("styles.css", "animations.css"):
        if not (site_dir / shared).exists():
            diags.append(_diag("completeness", shared, f"missing shared file {shared}"))

    for page in plan.pages:
        html = f"{page['slug']}.html"
        path = site_dir / html
        if not path.exists():
            diags.append(_diag("completeness", html, "page HTML missing"))
            continue
        if "<script" in path.read_text().lower():
            diags.append(_diag("no_js", html, "contains <script> (CSS-only required)"))

        try:
            r = render_filmstrip(site_dir, html)
        except Exception as exc:  # noqa: BLE001 - a page that won't render is a drop
            diags.append(_diag("renders", html, f"render failed: {exc}"))
            continue
        if r["n_animations"] <= 0:
            diags.append(_diag("animates", html, "no CSS animations declared"))
        elif not _frames_vary(r["frames"]):
            diags.append(_diag("animates", html, "page does not visibly animate over time"))
        if _is_blank(r["settled"]):
            diags.append(_diag("renders", html, "settled frame is blank"))

    return diags
