"""Command-line entrypoint for the grader (``python -m webdesign_rl.grade``).

This is the thin CLI the packaged Harbor task's ``tests/test.sh`` invokes inside
the verifier container: it renders the candidate HTML, grades it against the
committed reference screenshots, and writes ``reward.json`` /
``reward-details.json`` into the output directory (``/logs/verifier`` in Harbor).

All grading logic lives in :func:`webdesign_rl.grade.grader.grade`; this module
only parses arguments, loads the ``page_map`` JSON, and selects the judge:

- default: a live :class:`AnthropicJudgeClient` (needs ``ANTHROPIC_API_KEY`` and
  network egress) — the full four-term blend.
- ``--no-judge``: **deterministic-only** grading (``judge_client=None``), which
  drops the ``design_judge`` term and averages the three deterministic terms. No
  API key or egress required, so it is the robust primary oracle validation.

By default it also persists the exact rendered candidate pages it graded into
``<out>/renders/<page>.png`` (Harbor persists ``/logs/verifier``, so the graded
screenshots land in the job automatically), so reports use the same pixels that
produced each score; ``--no-save-renders`` opts out.
"""

import argparse
import contextlib
import json
import sys
import tempfile
from pathlib import Path

from .grader import grade


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl.grade",
        description="Grade a candidate HTML site against reference screenshots.",
    )
    parser.add_argument(
        "--candidate",
        required=True,
        help="Directory of the candidate's HTML/CSS/asset files (rendered here).",
    )
    reference = parser.add_mutually_exclusive_group(required=True)
    reference.add_argument(
        "--reference",
        help="Directory of pre-rendered reference screenshot PNGs.",
    )
    reference.add_argument(
        "--reference-site",
        help="Directory of the reference HTML site. The reference screenshots "
        "are rendered from it in-process with the same engine/fonts as the "
        "candidate, so an identical site scores an exact ~1.0 ceiling "
        "(host-independent — no committed-PNG font mismatch).",
    )
    parser.add_argument(
        "--page-map",
        required=True,
        help="JSON file mapping page -> {screenshot, expected_file}.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Directory to write reward.json and reward-details.json into.",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Deterministic-only grading: drop the design_judge term (no VLM "
        "call, no API key, no network egress).",
    )
    parser.add_argument(
        "--no-save-renders",
        dest="save_renders",
        action="store_false",
        help="Do not persist the graded candidate screenshots. By default the "
        "exact rendered candidate pages are written to <out>/renders/<page>.png "
        "so reports use the same pixels that produced the score.",
    )
    args = parser.parse_args(argv)

    page_map = json.loads(Path(args.page_map).read_text())

    if args.no_judge:
        judge_client = None
    else:
        from .judge import AnthropicJudgeClient

        judge_client = AnthropicJudgeClient()

    # Resolve the reference into a directory of PNGs. ``--reference-site`` renders
    # the reference HTML here, in the same process/engine/fonts as the candidate,
    # so the comparison is exactly apples-to-apples; ``--reference`` uses already
    # rendered PNGs. A TemporaryDirectory keeps the rendered reference scoped to
    # this run.
    with _resolve_reference(args, page_map) as reference_dir:
        reward = grade(
            args.candidate,
            reference_dir,
            page_map,
            args.out,
            judge_client,
            save_renders=args.save_renders,
        )
    # Echo the reward to stdout so it lands in the verifier's captured logs.
    print(json.dumps(reward))
    return 0


@contextlib.contextmanager
def _resolve_reference(args, page_map):
    """Yield a directory of reference PNGs for the chosen reference mode.

    ``--reference`` yields the given PNG dir as-is. ``--reference-site`` renders
    the reference HTML to a temporary PNG dir (named per ``page_map``) and yields
    that, cleaning it up afterward.
    """
    if args.reference is not None:
        yield args.reference
        return

    from ..render.browser import render_site

    with tempfile.TemporaryDirectory() as tmp:
        rendered = render_site(args.reference_site, page_map)
        for page, spec in page_map.items():
            rendered[page].save(Path(tmp) / spec["screenshot"])
        yield tmp


if __name__ == "__main__":
    sys.exit(main())
