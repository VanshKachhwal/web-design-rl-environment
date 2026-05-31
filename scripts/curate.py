"""CLI: curate a downloaded generation batch into a coverage-maximizing shortlist.

Point this at a downloaded batch dir (``out/batch-50-run1/``) — one seed dir per
seed, a survivor carrying an emitted ``task/`` and a gate drop only a ``site/`` —
and it filters to the survivors, optionally shortlists the coverage-maximizing
subset, COPIES the chosen survivor dirs into ``--out``, and prints the coverage
report. A human then eyeballs the shortlist + commits the final fixtures (the
HITL tail stays in issue 07).

This module is the **untested shell**: the filesystem copy + the print. Every
decision behind it — the survivor filter, the per-cell dedupe, the greedy
coverage shortlist, and the auditable coverage report — is the unit-tested pure
core in :mod:`webdesign_rl.generate.curate`.

Run::

    PYTHONPATH=src .venv/bin/python scripts/curate.py \\
        --batch out/batch-50-run1 --out out/curated-50
    PYTHONPATH=src .venv/bin/python scripts/curate.py \\
        --batch out/batch-50-run1 --out out/curated-50 --select 10 --spread 3,4,3
"""

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from webdesign_rl.generate import curate  # noqa: E402


def _parse_spread(text):
    """Parse a ``l,m,h`` spread string into a 3-int tuple (low/med/high)."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "--spread must be three comma-separated integers, e.g. 3,4,3"
        )
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError("--spread values must be integers")


def main(argv=None):  # pragma: no cover - thin I/O shell over the tested core.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--batch", required=True,
        help="downloaded batch dir (one seed dir per seed), e.g. out/batch-50-run1",
    )
    parser.add_argument(
        "--out", required=True,
        help="output dir to copy the curated survivors into, e.g. out/curated-50",
    )
    parser.add_argument(
        "--select", type=int, default=None,
        help="shortlist size N (default: keep all survivors, dedup only)",
    )
    parser.add_argument(
        "--spread", type=_parse_spread, default=curate.DEFAULT_COMPLEXITY_SPREAD,
        help="target complexity spread low,med,high (default: 3,4,3)",
    )
    args = parser.parse_args(argv)

    pool = curate.survivors(args.batch)
    if args.select is not None:
        chosen = curate.select_coverage(
            pool, n=args.select, complexity_spread=args.spread
        )
    else:
        # Default: keep all survivors, deduping same-cell duplicates only.
        chosen = curate.dedupe_by_cell(pool)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for survivor in chosen:
        dest = out_dir / survivor.seed_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(survivor.path, dest)

    report = curate.coverage_report(chosen)
    print(curate.format_coverage_report(report))
    print(f"\ncurated {len(chosen)} task(s) -> {out_dir}")


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint.
    main()
