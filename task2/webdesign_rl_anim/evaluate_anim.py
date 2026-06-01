"""Grade curated animation tasks at scale — the Task-2 ``eval-all`` (Task-1 parity).

Mirrors Task 1's ``scripts/evaluate_all.py`` + ``eval/run_claude_code.py``: over a
curated dir of tasks it runs **Claude Code + Opus 4.7, 10× per task** (``-k 10``,
``-n 10``), a few tasks in parallel (``--parallel 2``), on the chosen executor
(``modal`` for scale). For each task it prepares a throwaway eval copy that

1. **refreshes both baked grader packages** (``webdesign_rl`` and
   ``webdesign_rl_anim``) to *current* source — so a task emitted earlier on Modal
   still grades with the latest grader code (parity with Task 1's package refresh);
2. **flips only the agent env online** (Claude Code needs the API; the verifier env
   is left exactly as emitted).

The argv is built with Task 1's tested :func:`build_harbor_argv` (reused read-only):
``-a claude-code``, the one shared key on ``--ae``/``--ve``, ``--force-build`` (ships
the refreshed grader into the image). Pure/testable: ``_flip_agent_internet`` +
``prepare_eval_copy``. Untested shell: the subprocess/Harbor launch (the HITL step).
"""

import argparse
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from webdesign_rl.eval.run_claude_code import build_harbor_argv  # reused read-only

from .emit_anim import _T2_PKG, _copy_tree

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_EXECUTOR = "modal"
DEFAULT_ATTEMPTS = 10      # Task-1 parity: Claude Code 10× per task
DEFAULT_CONCURRENCY = 10   # -n per task
DEFAULT_PARALLEL = 2       # tasks graded concurrently (Task-1 parity)


def _flip_agent_internet(toml_text: str) -> str:
    """Set ``allow_internet = true`` in the ``[environment]`` table only."""
    def repl(match):
        return re.sub(r"allow_internet\s*=\s*false", "allow_internet = true",
                      match.group(0), count=1)
    return re.sub(r"\[environment\].*?(?=\n\[)", repl, toml_text, count=1, flags=re.DOTALL)


def _refresh_packages(dest: Path) -> None:
    """Re-bake both grader packages in the eval copy to CURRENT repo source.

    A task emitted earlier (e.g. on Modal, in-image) froze the grader at that time;
    refreshing here guarantees the verifier grades with the latest code. Task 1's
    ``_copy_package`` is WEBDESIGN_RL_PKG_ROOT-aware (works in dev and in-image).
    """
    from webdesign_rl.emit.task_builder import _copy_package

    pkg1 = dest / "tests" / "webdesign_rl_pkg"
    if pkg1.exists():
        shutil.rmtree(pkg1)
    _copy_package(pkg1)
    _copy_tree(_T2_PKG, dest / "tests" / "webdesign_rl_anim_pkg" / "webdesign_rl_anim")


def prepare_eval_copy(source_task_dir, dest_task_dir):
    """Clone a curated task to a throwaway eval copy: refresh graders + flip agent online."""
    source, dest = Path(source_task_dir), Path(dest_task_dir)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    _refresh_packages(dest)
    toml = dest / "task.toml"
    toml.write_text(_flip_agent_internet(toml.read_text()))
    return dest


def _task_dirs(tasks_path):
    """Resolve to a list of runnable Harbor task dirs (each containing task.toml).

    Accepts a single task dir, OR a curated dir whose entries are either the task
    dir directly (``<id>/task.toml``) or a Task-1-style seed dir holding the task
    under ``<id>/task/`` (curate keeps site/ + task/).
    """
    tasks_path = Path(tasks_path)
    if (tasks_path / "task.toml").exists():
        return [tasks_path]
    found = []
    for p in sorted(x for x in tasks_path.iterdir() if x.is_dir()):
        if (p / "task.toml").exists():
            found.append(p)
        elif (p / "task" / "task.toml").exists():
            found.append(p / "task")
    return found


def _job_name(task_dir: Path) -> str:
    """The seed-id-based job name: use the parent when the task dir is a ``task/``."""
    return task_dir.parent.name if task_dir.name == "task" else task_dir.name


def main(argv=None) -> int:  # pragma: no cover - subprocess/Harbor shell (HITL)
    import os

    ap = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.evaluate_anim",
        description="Eval-all: grade curated animation tasks with Claude Code + Opus 4.7, 10x each.",
    )
    ap.add_argument("--tasks", required=True, help="A single task dir or a curated dir of task dirs.")
    ap.add_argument("--out", default="task2/out/eval", help="Where eval copies are staged.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--executor", default=DEFAULT_EXECUTOR, help="docker | modal")
    ap.add_argument("--attempts", "-k", type=int, default=DEFAULT_ATTEMPTS)
    ap.add_argument("--concurrency", "-n", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL,
                    help="Tasks graded concurrently (each still uses -n for its own attempts).")
    ap.add_argument("--yes", action="store_true", help="Pass --yes to harbor (unattended).")
    a = ap.parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in the environment.", file=sys.stderr)
        return 2

    out_root = Path(a.out)
    out_root.mkdir(parents=True, exist_ok=True)
    tasks = _task_dirs(a.tasks)
    print(f"eval-all: {len(tasks)} task(s), -k {a.attempts} -n {a.concurrency} "
          f"on {a.executor}; --parallel {a.parallel}")

    def _grade_one(task_dir):
        name = _job_name(task_dir)
        try:
            eval_copy = prepare_eval_copy(task_dir, out_root / name)
            cmd = build_harbor_argv(
                task_path=eval_copy, job_name=f"anim-{name}", api_key=api_key,
                attempts=a.attempts, concurrency=a.concurrency,
                model=a.model, executor=a.executor, unattended=a.yes,
            )
            print(f"  launching {name} -> job anim-{name}")
            subprocess.run(cmd, check=True)
            return (name, "ok")
        except Exception as exc:  # noqa: BLE001 - one task failing must not sink the rest
            print(f"  ERROR grading {name}: {exc}", file=sys.stderr)
            return (name, f"errored: {exc}")

    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
        results = list(pool.map(_grade_one, tasks))

    print("\neval-all summary:")
    for name, status in results:
        print(f"  {name}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
