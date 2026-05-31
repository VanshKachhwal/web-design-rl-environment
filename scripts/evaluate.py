"""CLI: run the eval harness (Claude Code Opus 4.7 x10) on a curated task.

A thin argparse shell over :func:`webdesign_rl.eval.run_claude_code.launch` — the
same launch/CLI split ``modal_batch`` has over ``modal``. It clones the curated
task to a throwaway eval copy, refreshes the baked grader package to current code,
flips the *agent* environment online, and invokes ``harbor run`` (agent =
claude-code, model = Opus 4.7, attempts/concurrency default 10/10, executor =
modal, force-build, the shared ``ANTHROPIC_API_KEY`` from ``.env`` wired to both
the agent and the verifier judge). It only launches and prints the resulting
``jobs/<name>/`` path — eval and report are decoupled.

Run::

    PYTHONPATH=src .venv/bin/python scripts/evaluate.py \
        --task out/curated/004_local-service_luxury-serif_med/task \
        --name opus47-004
"""

import argparse
import sys

from webdesign_rl.eval import run_claude_code


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Launch an Opus-4.7-on-curated-task eval via Harbor.",
    )
    parser.add_argument(
        "--task", required=True,
        help="Path to the curated task dir to evaluate (cloned, never mutated).",
    )
    parser.add_argument(
        "--name", required=True,
        help="Job name (-> jobs/<name>/ and the eval-copy dir).",
    )
    parser.add_argument(
        "--attempts", type=int, default=run_claude_code.DEFAULT_ATTEMPTS,
        help="Number of attempts per trial (-k). Default 10.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=run_claude_code.DEFAULT_CONCURRENCY,
        help="Number of concurrent trials (-n). Default 10.",
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
        help="Auto-confirm Harbor's host-access prompt (--yes). Default "
             "interactive (a human confirms).",
    )
    args = parser.parse_args(argv)

    run_claude_code.launch(
        task_path=args.task,
        name=args.name,
        attempts=args.attempts,
        concurrency=args.concurrency,
        model=args.model,
        executor=args.executor,
        unattended=args.unattended,
    )


if __name__ == "__main__":
    sys.exit(main())
