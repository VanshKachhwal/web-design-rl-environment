"""Grade curated animation tasks at scale with Claude Code + Opus 4.7 via Harbor.

Mirrors Task 1's eval launcher: for each curated task it clones a throwaway eval
copy, flips the **agent** environment online (Claude Code needs the API; the
verifier env is left as emitted), builds the exact ``harbor run`` argv (reusing
Task 1's tested :func:`build_harbor_argv` read-only — same ``-a claude-code``,
shared key on ``--ae``/``--ve``, ``--force-build``), and subprocess-invokes Harbor
on the chosen executor (``modal`` for scale). One shared key drives the whole run.

Pure/testable: :func:`prepare_eval_copy` (clone + flip). Untested shell: the
subprocess/Harbor launch (the HITL step the user runs).
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from webdesign_rl.eval.run_claude_code import build_harbor_argv  # reused read-only

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_EXECUTOR = "modal"
DEFAULT_ATTEMPTS = 1       # the chosen default profile: -k 1
DEFAULT_CONCURRENCY = 10


def _flip_agent_internet(toml_text: str) -> str:
    """Set ``allow_internet = true`` in the ``[environment]`` table only."""
    def repl(match):
        block = match.group(0)
        return re.sub(r"allow_internet\s*=\s*false", "allow_internet = true", block, count=1)
    # Match the [environment] block up to the next [section] header.
    return re.sub(r"\[environment\].*?(?=\n\[)", repl, toml_text, count=1, flags=re.DOTALL)


def prepare_eval_copy(source_task_dir, dest_task_dir):
    """Clone a curated task to a throwaway eval copy with the agent env online."""
    source, dest = Path(source_task_dir), Path(dest_task_dir)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    toml = dest / "task.toml"
    toml.write_text(_flip_agent_internet(toml.read_text()))
    return dest


def _task_dirs(tasks_path):
    """Resolve ``tasks_path`` to a list of task dirs (a single task or a curated dir)."""
    tasks_path = Path(tasks_path)
    if (tasks_path / "task.toml").exists():
        return [tasks_path]
    return sorted(p for p in tasks_path.iterdir() if (p / "task.toml").exists())


def main(argv=None) -> int:  # pragma: no cover - subprocess/Harbor shell (HITL)
    import os

    ap = argparse.ArgumentParser(prog="python -m webdesign_rl_anim.evaluate_anim",
                                 description="Grade curated animation tasks via Harbor.")
    ap.add_argument("--tasks", required=True,
                    help="A single task dir or a curated dir of task dirs.")
    ap.add_argument("--out", default="task2/out/eval",
                    help="Where eval copies are staged.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--executor", default=DEFAULT_EXECUTOR, help="docker | modal")
    ap.add_argument("--attempts", "-k", type=int, default=DEFAULT_ATTEMPTS)
    ap.add_argument("--concurrency", "-n", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--yes", action="store_true", help="Pass --yes to harbor (unattended).")
    a = ap.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in the environment.", file=sys.stderr)
        return 2

    out_root = Path(a.out)
    out_root.mkdir(parents=True, exist_ok=True)

    for task_dir in _task_dirs(a.tasks):
        name = task_dir.name
        eval_copy = prepare_eval_copy(task_dir, out_root / name)
        argv_cmd = build_harbor_argv(
            task_path=eval_copy, job_name=f"anim-{name}", api_key=api_key,
            attempts=a.attempts, concurrency=a.concurrency,
            model=a.model, executor=a.executor, unattended=a.yes,
        )
        print(f"\n=== grading {name} -> job anim-{name} ===")
        print(" ".join(str(x) for x in argv_cmd).replace(api_key, "$ANTHROPIC_API_KEY"))
        subprocess.run(argv_cmd, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
