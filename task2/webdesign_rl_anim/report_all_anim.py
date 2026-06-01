"""Build the per-task animation model-eval report for EVERY job in a jobs dir.

Task-2 mirror of Task 1's ``scripts/report_all.py``: a thin, serial sweep over
:func:`webdesign_rl_anim.report_anim.build_report` — the *same* per-task report
``report_anim.py`` produces for one job, run once per discovered job. Reporting
is fast/cheap (no eval/grade), so it is its own command, decoupled from eval and
freely re-runnable; it **always regenerates** (no skip) so reports stay fresh
after a re-eval.

:func:`aggregate_results_anim.discover_jobs` finds the job dirs (direct children
carrying a ``result.json`` — never recursing into ``task__<id>/`` trial subdirs).
Failure isolation: one malformed job that fails to harvest/report is caught and
logged; the sweep continues, and an ``ok / failed`` tally prints at the end.

Run::

    PYTHONPATH=task2 .venv/bin/python -m webdesign_rl_anim.report_all_anim jobs/
    PYTHONPATH=task2 .venv/bin/python -m webdesign_rl_anim.report_all_anim jobs/ \
      --out-root task2/reports --format markdown
"""

import argparse
import sys
import traceback
from pathlib import Path

from .aggregate_results_anim import discover_jobs, is_anim_job
from .report_anim import build_report


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.report_all_anim",
        description="Build the animation model-eval report for every job in a dir.",
    )
    parser.add_argument(
        "jobs_dir",
        help="dir holding the jobs to report (e.g. jobs/); its direct children "
        "with a result.json are reported.",
    )
    parser.add_argument(
        "--out-root", default="task2/reports",
        help="root for per-job report dirs (default: task2/reports); each job "
        "writes to <out-root>/<job-name>/.",
    )
    parser.add_argument(
        "--format", choices=["html", "markdown"], default="html",
        help="report format for every job: 'html' (default) or 'markdown'.",
    )
    args = parser.parse_args(argv)

    out_root = Path(args.out_root)
    all_jobs = discover_jobs(args.jobs_dir)
    # A mixed jobs/ dir holds Task-1 STATIC jobs alongside the animation ones;
    # report only the animation jobs (the rest are skipped, not failed).
    jobs = [j for j in all_jobs if is_anim_job(j)]
    skipped = len(all_jobs) - len(jobs)
    if skipped:
        print(f"skipping {skipped} non-animation (static) job(s) under {args.jobs_dir}")
    if not jobs:
        print(f"No animation job dirs found under {args.jobs_dir}")
        return 0

    ok = failed = 0
    for job_dir in jobs:
        out_dir = out_root / job_dir.name
        try:
            build_report(job_dir, out_dir, fmt=args.format)
            print(f"ok   {job_dir.name} -> {out_dir}")
            ok += 1
        except Exception:  # noqa: BLE001 — isolate one job's failure; keep sweeping.
            failed += 1
            print(f"FAIL {job_dir.name}")
            traceback.print_exc()

    print(f"\nreport-all: {ok} ok, {failed} failed, {skipped} skipped "
          f"(of {len(all_jobs)} jobs)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
