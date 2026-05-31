"""CLI: build the per-task model-eval report for EVERY job in a jobs dir (EP-10).

A thin sweep over :func:`scripts.report.build_report` — the *same* per-task report
``report.py`` produces for one job, run once per job discovered under a jobs
directory. Reporting is fast/cheap (no eval/grade), so this is its own command,
**decoupled** from eval and freely re-runnable.

It does not re-implement reporting: the pure
:func:`webdesign_rl.eval.aggregate_results.discover_jobs` finds the job dirs (the
direct children carrying a ``result.json`` — never recursing into the
``task__<id>/`` trial subdirs), and each is driven through the existing
``build_report``. The sweep is **serial** (reports are cheap) and
**always-regenerates** (no skip — you want fresh reports after a re-eval).

Failure isolation: one malformed job that fails to harvest/report is caught and
logged; the sweep continues, and an ``ok / failed`` tally prints at the end. A
pre-EP-07 job WITHOUT ``verifier/reference_renders/`` is NOT a failure —
``build_report`` degrades gracefully (EP-07/08) and counts as ok.

No cross-task aggregate / index.html / summary.csv — deferred (per-task only).

Run::

    PYTHONPATH=src .venv/bin/python scripts/report_all.py jobs/
    PYTHONPATH=src .venv/bin/python scripts/report_all.py jobs/ --out-root reports/model-eval
"""

import argparse  # pragma: no cover
import sys  # pragma: no cover
import traceback  # pragma: no cover
from pathlib import Path  # pragma: no cover

from webdesign_rl.eval.aggregate_results import discover_jobs  # pragma: no cover


def main(argv=None):  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "jobs_dir",
        help="dir holding the jobs to report (e.g. jobs/); its direct children "
        "with a result.json are reported.",
    )
    parser.add_argument(
        "--out-root", default="reports/model-eval",
        help="root for per-job report dirs (default: reports/model-eval); each "
        "job writes to <out-root>/<job-name>/.",
    )
    args = parser.parse_args(argv)

    # Sibling-import build_report from report.py. scripts/ is not a package and
    # report.py is run as a script, so add this dir to the path and import by
    # name. Kept inside main() so importing this module stays clean/import-safe.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from report import build_report

    out_root = Path(args.out_root)
    jobs = discover_jobs(args.jobs_dir)
    if not jobs:
        print(f"No job dirs (subdirs with result.json) found under {args.jobs_dir}")
        return

    ok = 0
    failed = 0
    for job_dir in jobs:
        out_dir = out_root / job_dir.name
        try:
            build_report(job_dir, out_dir)
            print(f"ok   {job_dir.name} -> {out_dir}")
            ok += 1
        except Exception:  # noqa: BLE001 — isolate one job's failure; keep sweeping.
            failed += 1
            print(f"FAIL {job_dir.name}")
            traceback.print_exc()

    print(f"\nreport-all: {ok} ok, {failed} failed (of {len(jobs)} jobs)")


if __name__ == "__main__":  # pragma: no cover
    main()
