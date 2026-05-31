"""CLI: run the per-task eval (Opus 4.7 x10) over a whole curated batch.

A thin argparse + thread-pool shell over the EP-09 pure plan
(:func:`webdesign_rl.eval.batch.build_plan`) and the existing per-task launcher
(:func:`webdesign_rl.eval.run_claude_code.launch`). It does NOT re-implement the
eval — it discovers every survivor task in a curated dir (via
``curate.survivors``), builds an ordered plan (skip-completed, prefix, limit),
and drives ``launch`` once per to-run task through a thread pool of size
``--parallel``. Each task uses ``--concurrency`` for its own ``-n``, so
``--parallel 2`` x ``--concurrency 10`` = up to 20 concurrent agent sessions on
the one shared key (``--parallel 1`` backs it off to the validated baseline).

Failure isolation mirrors ``modal_batch.run_one_seed``: one task's launch failure
is logged and tallied, never aborting the batch — so a re-run (skip-completed)
retries only the failures. No cost estimate / confirmation prompt; it just runs.

Run::

    PYTHONPATH=src .venv/bin/python scripts/evaluate_all.py \
        --batch out/curated --parallel 2 --yes
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from webdesign_rl.eval import batch, run_claude_code


def main(argv=None):  # pragma: no cover - the untested thread-pool/Harbor shell.
    parser = argparse.ArgumentParser(
        description="Run the per-task Opus eval over every survivor in a "
                    "curated batch, a few in parallel.",
    )
    parser.add_argument(
        "--batch", required=True,
        help="Curated batch dir; every survivor task under it is evaluated.",
    )
    parser.add_argument(
        "--parallel", type=int, default=2,
        help="Number of evals to run concurrently (thread pool). Default 2.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=run_claude_code.DEFAULT_CONCURRENCY,
        help="Per-task concurrent trials (-n). Default 10.",
    )
    parser.add_argument(
        "--prefix", default="",
        help="Namespace prefix for job names (job_name = prefix + seed_id). "
             "Default '' (bare seed_id).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap the number of to-run (non-skipped) tasks.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run even tasks whose jobs/<job_name>/result.json exists.",
    )
    parser.add_argument(
        "--attempts", type=int, default=run_claude_code.DEFAULT_ATTEMPTS,
        help="Attempts per trial (-k). Default 10.",
    )
    parser.add_argument(
        "--model", default=run_claude_code.DEFAULT_MODEL,
        help="Agent model. Default claude-opus-4-7.",
    )
    parser.add_argument(
        "--executor", default=run_claude_code.DEFAULT_EXECUTOR,
        help="Harbor environment/executor (-e). Default modal.",
    )
    parser.add_argument(
        "--yes", "--unattended", dest="unattended", action="store_true",
        help="Auto-confirm Harbor's host-access prompt (--yes) for each task.",
    )
    args = parser.parse_args(argv)

    plans = batch.build_plan(
        args.batch,
        run_claude_code.DEFAULT_JOBS_DIR,
        prefix=args.prefix,
        force=args.force,
        limit=args.limit,
    )
    to_run = [p for p in plans if not p.skip]
    skipped = [p for p in plans if p.skip]

    print(
        f"batch eval: {len(to_run)} to run, {len(skipped)} skipped "
        f"(of {len(plans)} survivors); --parallel {args.parallel} "
        f"x --concurrency {args.concurrency}",
        file=sys.stderr,
    )

    def _run_one(plan):
        """Launch one task's eval; isolate any failure as a recorded error."""
        try:
            run_claude_code.launch(
                task_path=plan.task_path,
                name=plan.job_name,
                attempts=args.attempts,
                concurrency=args.concurrency,
                model=args.model,
                executor=args.executor,
                unattended=args.unattended,
            )
            return plan.seed_id, None
        except Exception as exc:  # noqa: BLE001 - isolate ALL per-task failures.
            print(f"task {plan.seed_id} FAILED: {exc}", file=sys.stderr)
            return plan.seed_id, exc

    ok, failed = [], []
    if to_run:
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            for seed_id, exc in pool.map(_run_one, to_run):
                (failed if exc is not None else ok).append(seed_id)

    print(
        f"\nbatch eval done: {len(ok)} ok, {len(failed)} failed, "
        f"{len(skipped)} skipped.",
        file=sys.stderr,
    )
    if failed:
        print(f"  failed: {', '.join(sorted(failed))}", file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
