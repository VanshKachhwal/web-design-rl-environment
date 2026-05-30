"""Generate the committed PNG image fixtures for the grader tests.

Run with::

    .venv/bin/python tests/fixtures/_generate.py

The fixtures are hand-made (solid blocks / simple shapes) and fully deterministic
so the same bytes are produced every run and can be committed. Regenerate only
when the fixture design intentionally changes.

Layout produced under tests/fixtures/::

    reference/home.png              structured reference home page
    reference/about.png            a distinct second reference page
    candidate_perfect/home.png      byte-identical copy of the reference home
    candidate_blurred/home.png      blurred home (lower structure)
    candidate_different/home.png    unrelated image (much lower structure)
    candidate_multipage/home.png    perfect home; about.png intentionally absent
    text/reference.png              large dark text on white (legible to OCR)
    site_render_reference/home.png  the live-render grader's reference screenshot,
                                    rendered once from site_reference/ (issue 05)

The ``text`` page is rendered with a real TrueType font at a large size so
Tesseract OCR reads it reliably; the ``content`` OCR-legibility test reads it
back and asserts the expected words come out (proving the fixture is not
silently empty).

The live-render grader path (issue 05) also uses committed *HTML* site fixtures
that are not produced here (they are hand-authored static files committed under
``tests/fixtures/``):

    site_reference/    the hand-made reference site (HTML/CSS/logo.png)
    site_perfect/      byte-copy of site_reference (the "perfect" candidate)
    site_wrongcolor/   same layout/text, wrong palette (degraded candidate)
    site_missing/      home present, about.html intentionally absent
    site_external/     references an unroutable external host (offline test)

Only the rendered ``site_render_reference/home.png`` is generated from them, by
``build_site_reference_png`` below.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent

# A real system TrueType font; large size keeps OCR reliable. Arial ships on
# macOS at this path; document the choice so a different host can swap it.
_FONT_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
# The exact words rendered into text/reference.png, in order. The legibility
# test imports this so the fixture and its expectation can't drift apart.
TEXT_LINES = ("Welcome Home", "Get Started Today")


def reference_page() -> Image.Image:
    """A simple, structured reference page: solid blocks on a white background."""
    arr = np.full((120, 96), 255, dtype=np.uint8)
    arr[10:30, 10:86] = 40     # header bar
    arr[40:70, 10:46] = 120    # left block
    arr[40:70, 50:86] = 180    # right block
    arr[80:110, 10:86] = 60    # footer bar
    return Image.fromarray(arr).convert("RGB")


def different_page() -> Image.Image:
    """An unrelated image (vertical stripes) for the clearly-different case."""
    stripes = np.zeros((120, 96), dtype=np.uint8)
    stripes[:, ::3] = 255
    return Image.fromarray(stripes).convert("RGB")


def text_page() -> Image.Image:
    """Large dark text on a white background — legible to Tesseract OCR."""
    font = ImageFont.truetype(_FONT_PATH, 40)
    img = Image.new("RGB", (640, 360), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(TEXT_LINES):
        draw.text((20, 20 + i * 60), line, fill=(0, 0, 0), font=font)
    return img


def build(root: Path = ROOT) -> None:
    reference = reference_page()

    def save(img: Image.Image, *parts: str) -> None:
        path = root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)

    save(reference, "reference", "home.png")
    # A distinct second page so multi-page aggregation has real content.
    save(reference.transpose(Image.Transpose.FLIP_TOP_BOTTOM), "reference", "about.png")

    save(reference, "candidate_perfect", "home.png")
    save(reference.filter(ImageFilter.GaussianBlur(3)), "candidate_blurred", "home.png")
    save(different_page(), "candidate_different", "home.png")

    # Multi-page candidate: home present and perfect, about.png intentionally absent.
    save(reference, "candidate_multipage", "home.png")

    # A legible text page for the OCR-legibility test.
    save(text_page(), "text", "reference.png")

    build_site_reference_png(root)


def build_site_reference_png(root: Path = ROOT) -> None:
    """Render the committed reference screenshot for the live-render grader path.

    The grader (issue 05) renders the candidate *HTML* itself but compares it to
    a committed reference *PNG* — "the screenshots shown to the agent". That PNG
    is produced once, here, by rendering the hand-made ``site_reference/`` with
    the same render module the grader uses, so reference and candidate are
    apples-to-apples (same viewport, same offline determinism). Regenerate only
    when the reference site intentionally changes.
    """
    # Imported here (not at module top) so the cheap PIL fixtures above don't
    # pull in Playwright when only those are needed.
    from webdesign_rl.render.browser import render_site

    site = root / "site_reference"
    page_map = {"home": {"expected_file": "index.html"}}
    image = render_site(site, page_map, viewport=1280)["home"]
    out = root / "site_render_reference"
    out.mkdir(parents=True, exist_ok=True)
    image.save(out / "home.png")


if __name__ == "__main__":
    build()
    print(f"Wrote fixtures under {ROOT}")
