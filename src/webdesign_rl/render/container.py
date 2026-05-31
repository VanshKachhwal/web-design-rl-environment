"""Render a site to screenshots **inside the sealed verifier image**.

:func:`render_in_container` is the in-container counterpart of
:func:`webdesign_rl.render.browser.render_site`. It exists for one reason: the
agent's reference screenshots must be produced in the *same* environment that
grades the candidate — the curated font palette installed OS-level, the pinned
Chromium, the offline render — so the typography the agent studies is exactly the
typography it is graded against. Rendering on the macOS host instead silently
substitutes host fonts and reintroduces the issue-07/09 host/container drift this
whole slice exists to kill.

Mechanism: build a render image (the verifier image's Python + package +
Chromium + OS-level font palette, with no grader inputs baked in), then run the
render CLI (``python -m webdesign_rl.render``) inside it with the site mounted
read-only and an output directory mounted read-write. The produced PNGs are read
back into :class:`PIL.Image` objects, so the return type matches ``render_site``
and it is a drop-in renderer for :func:`webdesign_rl.emit.build_task`.

Docker is required (build-time has network to fetch the pinned fonts; the render
step runs ``--network none``). The image is content-addressed by a tag derived
from the package + Dockerfile so repeated emits reuse a cached build.
"""

import io
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from ..generate import fonts

# The render image's tag. A fixed name is fine: Docker's layer cache keys on the
# build context + Dockerfile, so an unchanged package/palette reuses the build.
RENDER_IMAGE_TAG = "webdesign-rl-render:latest"

# A render-only Dockerfile: the verifier image's system deps + font palette +
# package + Chromium, but none of the grader inputs (reference_site/page_map/
# test.sh) — those are grading concerns, not rendering. Reuses the verifier
# template's font-palette install verbatim so there is zero drift between the
# image that renders the agent screenshots and the image that grades.
_RENDER_DOCKERFILE = f"""\
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        fonts-dejavu-core \\
        fontconfig \\
        ca-certificates \\
        curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && fc-cache -f

{fonts.dockerfile_install_block()}

COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]
RUN playwright install --with-deps chromium
"""


def _docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, **kwargs)


def build_render_image(tag: str = RENDER_IMAGE_TAG) -> str:
    """Build the sealed render image (package + Chromium + OS-level font palette).

    Returns the built image's ``tag``. Idempotent and cache-friendly: an
    unchanged package + palette reuses Docker's layer cache.
    """
    # Local import to avoid a package-level import cycle (task_builder imports
    # this module; that module copies the package for baking).
    from ..emit.task_builder import _copy_package

    with tempfile.TemporaryDirectory() as ctx:
        ctx = Path(ctx)
        _copy_package(ctx / "webdesign_rl_pkg")
        (ctx / "Dockerfile").write_text(_RENDER_DOCKERFILE)
        _docker("build", "-t", tag, str(ctx))
    return tag


def render_in_container(site_dir, page_map, viewport: int = 1280, *,
                        tag: str = RENDER_IMAGE_TAG, build: bool = True):
    """Render each page of ``site_dir`` inside the sealed render image.

    Drop-in replacement for :func:`render_site`: same ``(site_dir, page_map,
    viewport)`` signature, same ``{page: PIL.Image}`` return — but the render
    happens inside the image (OS-level font palette) rather than on the host, so
    the agent's reference screenshots carry the design's intended typography, not
    a host-font substitution.

    Args:
        site_dir, page_map, viewport: as :func:`render_site`.
        tag: the render image tag to run (built first when ``build`` is true).
        build: build/refresh the image before rendering (set false to reuse an
            already-built tag, e.g. across a batch of sites).
    """
    site_dir = Path(site_dir).resolve()
    if build:
        build_render_image(tag)

    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / "page_map.json").write_text(json.dumps(page_map))
        shots = work / "shots"
        shots.mkdir()

        _docker(
            "run", "--rm", "--network", "none",
            "-v", f"{site_dir}:/site:ro",
            "-v", f"{work}:/work",
            tag,
            "python", "-m", "webdesign_rl.render",
            "--site", "/site",
            "--page-map", "/work/page_map.json",
            "--out", "/work/shots",
            "--viewport", str(viewport),
        )

        images = {}
        for page_name, spec in page_map.items():
            png = shots / spec["screenshot"]
            if png.exists():
                images[page_name] = Image.open(io.BytesIO(png.read_bytes())) \
                    .convert("RGB")
    return images
