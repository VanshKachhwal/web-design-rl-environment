"""Docker-gated test for in-container rendering with the OS-level font palette.

The unit core (manifest, gate check, prompt, render CLI, the injected-render
seam) is Docker-free and covered elsewhere. This test is the real end-to-end
proof of issue 05's image side: build the sealed render image and confirm (1) the
curated palette actually resolves by **bare family name** inside it (not DejaVu
fallback), and (2) :func:`render_in_container` returns one screenshot per page.

It is skipped when Docker is unavailable so the fast suite stays green; run it
locally / in CI on a Docker host (it builds an image + fetches the pinned fonts,
so it is slow — a few minutes on a cold cache).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_SITE = FIXTURES / "site5_reference"

PAGE_MAP = {
    "home": {"screenshot": "home.png", "expected_file": "index.html"},
    "about": {"screenshot": "about.png", "expected_file": "about.html"},
}


def _docker_available():
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "info"], check=True,
                       capture_output=True, timeout=30)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker not available; in-container render is Docker-gated.",
)


@pytest.fixture(scope="module")
def render_image():
    from webdesign_rl.render.container import build_render_image
    return build_render_image()


def test_palette_resolves_by_bare_name_inside_the_image(render_image):
    # fc-list inside the image must list the palette families by bare name, so a
    # site's `font-family: Inter` resolves OS-level rather than to DejaVu.
    from webdesign_rl.generate import fonts

    out = subprocess.run(
        ["docker", "run", "--rm", render_image, "fc-list", ":", "family"],
        check=True, capture_output=True, text=True,
    ).stdout

    for family in fonts.PALETTE_FAMILIES:
        assert family in out, f"{family} not installed in render image:\n{out}"


def test_render_in_container_returns_one_image_per_page(render_image, tmp_path):
    from webdesign_rl.render.container import render_in_container

    images = render_in_container(REFERENCE_SITE, PAGE_MAP, build=False)

    assert set(images) == set(PAGE_MAP)
    for image in images.values():
        assert image.width == 1280
