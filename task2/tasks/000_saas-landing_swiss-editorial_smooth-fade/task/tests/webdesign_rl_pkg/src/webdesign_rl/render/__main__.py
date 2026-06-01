"""Render a site directory to per-page PNGs (``python -m webdesign_rl.render``).

The thin CLI the **in-container** agent-screenshot renderer
(:func:`webdesign_rl.render.container.render_in_container`) invokes *inside* the
sealed verifier image: it serves ``--site``, renders each page named in the
``--page-map`` at ``--viewport``, and writes one PNG per page (named by the
page's ``screenshot`` field) into ``--out``. Running it in the verifier image is
what makes the agent's reference screenshots come from the same engine + OS-level
font palette as grading, so the typography the agent studies is the typography it
is graded against (issue 05).

All rendering lives in :func:`webdesign_rl.render.browser.render_site`; this
module only parses arguments, loads the ``page_map``, and saves the images.
"""

import argparse
import json
from pathlib import Path

from .browser import render_site


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl.render",
        description="Render a site directory to one screenshot PNG per page.",
    )
    parser.add_argument(
        "--site", required=True,
        help="Directory of HTML/CSS/asset files to serve and render.",
    )
    parser.add_argument(
        "--page-map", required=True,
        help="JSON file mapping page -> {screenshot, expected_file}.",
    )
    parser.add_argument(
        "--out", required=True,
        help="Directory to write one <screenshot>.png per page into.",
    )
    parser.add_argument(
        "--viewport", type=int, default=1280,
        help="Capture width in CSS pixels (default 1280).",
    )
    args = parser.parse_args(argv)

    page_map = json.loads(Path(args.page_map).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    images = render_site(args.site, page_map, viewport=args.viewport)
    for page_name, spec in page_map.items():
        image = images.get(page_name)
        if image is None:
            raise SystemExit(
                f"site has no renderable page for '{page_name}' "
                f"(expected_file={spec.get('expected_file')!r})"
            )
        image.save(out / spec["screenshot"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
