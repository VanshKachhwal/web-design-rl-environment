"""Local single-site spike CLI (``python -m webdesign_rl.generate``).

The issue-01 "generate one site locally and eyeball it" command: it runs the
3-stage pipeline for a single seed through the live
:class:`AnthropicGenerationClient` (Opus 4.6), writes the site to a directory,
then renders one full-page 1280px screenshot per page with the *existing* render
module so the result can be reviewed by eye.

Usage::

    # one site from an explicit seed, written to ./out/site, screenshots to ./out/shots
    python -m webdesign_rl.generate \\
        --archetype "tea-shop" --aesthetic "warm-minimal" --complexity low \\
        --out ./out/site --screenshots ./out/shots

``ANTHROPIC_API_KEY`` must be set (loaded from ``.env`` like the rest of the
project). The deterministic logic is covered by the stubbed pipeline tests; this
CLI is the live, human-review path and is intentionally not unit-tested.
"""

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl.generate",
        description="Generate one site end-to-end (Opus 4.6) and render it locally.",
    )
    parser.add_argument("--archetype", default="tea-shop", help="Site archetype seed axis.")
    parser.add_argument("--aesthetic", default="warm-minimal", help="Aesthetic seed axis.")
    parser.add_argument(
        "--complexity",
        default="med",
        choices=["low", "med", "high"],
        help="Layout-complexity seed axis (couples to page count later).",
    )
    parser.add_argument("--audience", default=None, help="Optional audience/region modifier.")
    parser.add_argument("--brand-mood", default=None, dest="brand_mood", help="Optional brand-mood modifier.")
    parser.add_argument(
        "--out",
        required=True,
        help="Directory to write the generated site (HTML/CSS + page_map.json).",
    )
    parser.add_argument(
        "--screenshots",
        default=None,
        help="Directory to render one full-page 1280px PNG per page into for "
        "visual review (defaults to <out>/_screenshots).",
    )
    args = parser.parse_args(argv)

    # Load .env so ANTHROPIC_API_KEY is available, matching the rest of the project.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from ..render.browser import render_site
    from .client import AnthropicGenerationClient
    from .llm_site_generator import generate_site

    seed = {
        "archetype": args.archetype,
        "aesthetic": args.aesthetic,
        "complexity": args.complexity,
    }
    if args.audience:
        seed["audience"] = args.audience
    if args.brand_mood:
        seed["brand_mood"] = args.brand_mood

    site_dir = generate_site(seed, client=AnthropicGenerationClient(), out_dir=args.out)
    page_map = json.loads((site_dir / "page_map.json").read_text())

    shots_dir = Path(args.screenshots) if args.screenshots else site_dir / "_screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    images = render_site(site_dir, page_map, viewport=1280)
    for page, spec in page_map.items():
        images[page].save(shots_dir / spec["screenshot"])

    print(
        json.dumps(
            {
                "site_dir": str(site_dir),
                "screenshots_dir": str(shots_dir),
                "pages": list(page_map),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
