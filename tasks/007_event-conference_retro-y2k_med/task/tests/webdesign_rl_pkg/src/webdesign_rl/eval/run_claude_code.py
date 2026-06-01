"""Launch Claude Code (Opus 4.7) on a curated task N times via ``harbor run``.

This replaces a hand-typed mega-command: a single call clones the curated task to
a throwaway eval copy, refreshes the baked grader package to current source, flips
the *agent* environment online (so the in-sandbox agent can reach the API while
the shipped task stays offline), and invokes Harbor with the right flags.

Split exactly like :mod:`webdesign_rl.generate.modal_batch`:

- a **pure, unit-tested core** (no Harbor / Modal / network): :func:`build_harbor_argv`
  (the exact ``harbor run`` argv for given params) and :func:`prepare_eval_copy`
  (clone → refresh package → flip agent internet, never mutating the source); and

- a **thin shell** at the bottom (:func:`launch`): loads the shared key from
  ``.env``, runs the prep, builds the argv, and ``subprocess``-invokes ``harbor``,
  printing the resulting ``jobs/<name>/`` path. ``subprocess`` is the untested
  shell — exactly like ``modal_batch``'s lazy Modal wrapper.

The module stays import-safe with neither Harbor nor Modal installed: nothing at
module top imports them.
"""

# Defaults: 10 attempts at concurrency 10 under one shared key (the eval-side
# number that matches the generation batch — see modal_batch.DEFAULT_CONCURRENCY).
DEFAULT_ATTEMPTS = 10
DEFAULT_CONCURRENCY = 10
DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_EXECUTOR = "modal"


def build_harbor_argv(
    *,
    task_path,
    job_name,
    api_key,
    attempts: int = DEFAULT_ATTEMPTS,
    concurrency: int = DEFAULT_CONCURRENCY,
    model: str = DEFAULT_MODEL,
    executor: str = DEFAULT_EXECUTOR,
    unattended: bool = False,
):
    """Build the exact ``harbor run`` argv for an Opus-on-curated-task eval.

    Pure: no Harbor, no I/O. The one shared ``api_key`` is wired to **both** the
    agent (``--ae``) and the verifier judge (``--ve``), so a single key drives the
    whole run. ``--force-build`` ships the freshly-refreshed grader into the image.
    ``--yes`` is appended only when ``unattended`` (default interactive, so a human
    confirms Harbor's host-access prompt).
    """
    agent_env = f"ANTHROPIC_API_KEY={api_key}"
    argv = [
        "harbor", "run",
        "-a", "claude-code",
        "-m", str(model),
        "-p", str(task_path),
        "-e", str(executor),
        "--force-build",
        "-k", str(attempts),
        "-n", str(concurrency),
        "--ae", agent_env,
        "--ve", agent_env,
        "--job-name", str(job_name),
    ]
    if unattended:
        argv.append("--yes")
    return argv


def prepare_eval_copy(source_task_dir, dest_task_dir):
    """Clone a curated task to a throwaway eval copy ready for an Opus run.

    Pure (filesystem only, no Harbor / Modal / network). In order:

    1. **Clone** ``source_task_dir`` to ``dest_task_dir`` — the shipped/curated
       task is never mutated. An existing destination is cleared first.
    2. **Refresh the baked grader package**: clean-overwrite the frozen
       ``tests/webdesign_rl_pkg`` snapshot with the *current* repo source via
       :func:`~webdesign_rl.emit.task_builder._copy_package`, clearing the old
       package dir first so a since-deleted module can't linger. The verifier then
       grades with current code, not whatever was frozen at emit time.
    3. **Flip the agent env online**: set ``[environment].allow_internet = true``
       in the copy's ``task.toml`` (so the in-sandbox agent can reach the API),
       leaving ``[verifier.environment]`` exactly as emitted.

    Returns the ``Path`` to the prepared eval copy.
    """
    import shutil
    from pathlib import Path

    from ..emit.task_builder import _copy_package

    source = Path(source_task_dir)
    dest = Path(dest_task_dir)

    # (1) Clone — never touch the source.
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )

    # (2) Refresh the baked grader package to current source. Clear the old
    # package dir first so a since-deleted module can't survive into the copy.
    baked_pkg = dest / "tests" / "webdesign_rl_pkg"
    if baked_pkg.exists():
        shutil.rmtree(baked_pkg)
    _copy_package(baked_pkg)

    # (3) Flip ONLY the agent env online, leaving the verifier env untouched.
    task_toml = dest / "task.toml"
    task_toml.write_text(
        _flip_agent_internet(task_toml.read_text())
    )

    return dest


def _flip_agent_internet(toml_text: str) -> str:
    """Set ``allow_internet = true`` in the ``[environment]`` table only.

    Edits the line in place, scoped to the agent's ``[environment]`` table, so
    the ``[verifier.environment]`` table's own ``allow_internet`` is never
    touched. A line-scoped edit (not a full toml round-trip) preserves the file's
    comments and formatting; ``tomllib`` is write-free, so a serializer would lose
    them. A ``[environment]`` table is required (it is in every emitted task).
    """
    lines = toml_text.splitlines(keepends=True)
    in_agent_env = False
    flipped = False
    for i, line in enumerate(lines):
        header = line.strip()
        if header.startswith("[") and header.endswith("]"):
            in_agent_env = header == "[environment]"
            continue
        if in_agent_env and line.split("#", 1)[0].lstrip().startswith(
            "allow_internet"
        ):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = f"{indent}allow_internet = true\n"
            flipped = True
            break
    if not flipped:
        raise ValueError(
            "task.toml has no [environment].allow_internet line to flip"
        )
    return "".join(lines)


# ---------------------------------------------------------------------------
# Thin shell — NOT unit-tested. ``subprocess``/``harbor`` are exercised only in
# the live run, exactly like ``modal_batch``'s lazy Modal wrapper. This loads the
# shared key from ``.env``, runs the prep (tested above), builds the argv (tested
# above), and shells out to ``harbor``. The live invocation is the HITL step.
# ---------------------------------------------------------------------------

# Where the eval copy and the job land by convention (relative to the cwd, like
# the rest of the project's ``out/`` and ``jobs/`` directories).
DEFAULT_EVAL_ROOT = "out/eval"
DEFAULT_JOBS_DIR = "jobs"


def launch(
    *,
    task_path,
    name,
    attempts: int = DEFAULT_ATTEMPTS,
    concurrency: int = DEFAULT_CONCURRENCY,
    model: str = DEFAULT_MODEL,
    executor: str = DEFAULT_EXECUTOR,
    unattended: bool = False,
    eval_root=DEFAULT_EVAL_ROOT,
):  # pragma: no cover - the untested subprocess/Harbor shell.
    """Prepare an eval copy and launch ``harbor run`` on it; print the job path.

    The untested shell: loads ``ANTHROPIC_API_KEY`` from ``.env`` (matching the
    rest of the project), runs :func:`prepare_eval_copy` (clone → refresh package →
    flip agent internet), builds the argv via :func:`build_harbor_argv`, and
    ``subprocess``-invokes ``harbor``. It only **launches** — it does not
    wait-and-report (eval and report are decoupled). Prints the resulting
    ``jobs/<name>/`` path and returns it.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    # Load .env so ANTHROPIC_API_KEY is available, matching the rest of the project.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set (load it from .env). It is the one "
            "shared key wired to both the agent and the verifier judge."
        )

    eval_copy = prepare_eval_copy(
        Path(task_path), Path(eval_root) / name / "task"
    )

    argv = build_harbor_argv(
        task_path=str(eval_copy),
        job_name=name,
        api_key=api_key,
        attempts=attempts,
        concurrency=concurrency,
        model=model,
        executor=executor,
        unattended=unattended,
    )

    print(f"Launching Harbor eval: {' '.join(argv[:2])} ...", file=sys.stderr)
    subprocess.run(argv, check=True)

    job_path = Path(DEFAULT_JOBS_DIR) / name
    print(job_path)
    return job_path
