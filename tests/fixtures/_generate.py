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
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).parent


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


if __name__ == "__main__":
    build()
    print(f"Wrote fixtures under {ROOT}")
