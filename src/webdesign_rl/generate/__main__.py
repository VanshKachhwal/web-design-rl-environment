"""Local single-site spike CLI (``python -m webdesign_rl.generate``).

The build-order "generate one site locally and eyeball it" command. It runs the
**full gated pipeline** for a single seed through the live
:class:`AnthropicGenerationClient` (Opus 4.6) — stage 1->2->3 + inline gates +
stage 4/5 quality gate + bounded composition-only repair — writes the gated site
to a directory, renders one full-page 1280px screenshot per page with the
*existing* render module so the result can be reviewed by eye, and optionally
emits a runnable Harbor task.

The seed is a real taxonomy point: pass explicit axes (validated against the
taxonomy) or ``--seed-index N`` to use the Nth stratified-sample seed.

Usage::

    # the first stratified seed (saas-landing / swiss-editorial / low = 5 pages)
    python -m webdesign_rl.generate --seed-index 0 \\
        --out ./out/site --screenshots ./out/shots

    # an explicit seed, and also emit a runnable Harbor task
    python -m webdesign_rl.generate \\
        --archetype restaurant-hospitality --aesthetic warm-organic --complexity low \\
        --out ./out/site --screenshots ./out/shots --emit ./out/task

``ANTHROPIC_API_KEY`` must be set (loaded from ``.env`` like the rest of the
project). The pipeline makes ~a dozen live model calls per site (stage 1 + stage
2 + one per page + any repair nudges). The deterministic logic is covered by the
stubbed pipeline tests; this CLI is the live, human-review path and is
intentionally not unit-tested.

Note: the font palette (issue 05) is installed OS-level in the verifier/render
image, so a site's ``font-family: Inter`` resolves by bare name. ``--emit`` renders
the agent's reference screenshots **in-container** (the same sealed image + font
palette as grading), which needs Docker available on the host.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from . import taxonomy
from .seeds import Seed, expand_seed, sample_seeds


def _build_seed(args) -> Seed:
    """Resolve CLI args into a real taxonomy :class:`Seed`."""
    if args.seed_index is not None:
        # The Nth stratified-sample seed (deterministic, spans the grid).
        return sample_seeds(args.seed_index + 1)[args.seed_index]
    return Seed(
        archetype=args.archetype,
        aesthetic=args.aesthetic,
        complexity=args.complexity,
        audience=args.audience or taxonomy.AUDIENCES[0],
        brand_mood=args.brand_mood or taxonomy.BRAND_MOODS[0],
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl.generate",
        description="Generate one site end-to-end through the gated pipeline "
        "(Opus 4.6) and render it locally for review.",
    )
    parser.add_argument(
        "--seed-index",
        type=int,
        default=None,
        help="Use the Nth stratified-sample seed (overrides the explicit axes). "
        "Index 0 is the first spanning seed.",
    )
    parser.add_argument(
        "--archetype",
        default=taxonomy.ARCHETYPES[0],
        choices=taxonomy.ARCHETYPES,
        help="Site archetype (drives the sitemap).",
    )
    parser.add_argument(
        "--aesthetic",
        default=taxonomy.AESTHETICS[0],
        choices=taxonomy.AESTHETICS,
        help="Visual aesthetic (drives the design system).",
    )
    parser.add_argument(
        "--complexity",
        default="med",
        choices=taxonomy.COMPLEXITIES,
        help="Layout-complexity (couples to page count: low~5, med~7, high~10).",
    )
    parser.add_argument("--audience", default=None, help="Optional audience/region modifier.")
    parser.add_argument(
        "--brand-mood", default=None, dest="brand_mood", help="Optional brand-mood modifier."
    )
    parser.add_argument(
        "--out", required=True, help="Directory to write the gated site (HTML/CSS + page_map.json)."
    )
    parser.add_argument(
        "--screenshots",
        default=None,
        help="Directory to render one full-page 1280px PNG per page into for visual "
        "review (defaults to <out>/_screenshots).",
    )
    parser.add_argument(
        "--emit",
        default=None,
        help="Optional: also package a runnable Harbor task into this directory.",
    )
    args = parser.parse_args(argv)

    # Install a handler at the entrypoint so the pipeline's INFO progress logs are
    # actually shown (library code only emits; it must not configure logging).
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load .env so ANTHROPIC_API_KEY is available, matching the rest of the project.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    from ..render.browser import render_site
    from .client import AnthropicGenerationClient
    from .llm_site_generator import Dropped, generate_gated_site

    seed = _build_seed(args)
    spec = expand_seed(seed)
    print(
        f"Generating: archetype={seed.archetype} aesthetic={seed.aesthetic} "
        f"complexity={seed.complexity} ({spec['page_count']} pages) ...",
        file=sys.stderr,
    )

    result = generate_gated_site(spec, client=AnthropicGenerationClient(), out_dir=args.out)
    if isinstance(result, Dropped):
        print(json.dumps({"status": "dropped", "reason": result.reason}, indent=2))
        return 1

    site_dir = result
    page_map = json.loads((site_dir / "page_map.json").read_text())

    shots_dir = Path(args.screenshots) if args.screenshots else site_dir / "_screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    images = render_site(site_dir, page_map, viewport=1280)
    for page, page_spec in page_map.items():
        images[page].save(shots_dir / page_spec["screenshot"])

    out = {
        "status": "ok",
        "seed": list(seed),
        "site_dir": str(site_dir),
        "screenshots_dir": str(shots_dir),
        "pages": list(page_map),
    }

    if args.emit:
        from ..emit.task_builder import build_task

        build_task(site_dir, page_map, args.emit)
        out["task_dir"] = str(args.emit)

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
