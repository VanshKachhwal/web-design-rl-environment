"""Behavioral tests for the eval launcher's pure core (EP-02).

The launcher runs Claude Code + Opus 4.7 on a curated task N times on Modal via
``harbor run`` — replacing a hand-typed mega-command. The same split as
``modal_batch``: the ``subprocess`` invocation of ``harbor`` is an untested, thin,
lazy shell; everything that decides *what* runs — the **argv builder** and the
**clone-flip-refresh** prep — is a pure core unit-tested here with fixtures, no
Harbor / Modal / network.

We assert external behavior: the exact ``harbor run`` argv list for given params,
and the on-disk state of a prepared eval copy (distinct from the source, agent env
internet flipped, verifier env untouched, baked package refreshed) — plus that the
module imports without Harbor or Modal installed.
"""

import tomllib
from pathlib import Path

from webdesign_rl.eval import run_claude_code


# --- A tiny fixture curated task: just the two allow_internet lines + a stub
# baked package, so the clone-flip-refresh tests are fast, offline, and self-
# contained (no real curated task copied in). ---------------------------------

_FIXTURE_TASK_TOML = """\
schema_version = "1.2"

[task]
name = "webdesign-rl/replicate-site"

[environment]
# The AGENT environment: offline by design in the shipped task.
allow_internet = false
cpus = 2

[verifier]
environment_mode = "separate"

[verifier.environment]
# The VERIFIER environment: online for the judge — must stay untouched.
allow_internet = true
cpus = 2
"""


def _make_fixture_task(root: Path) -> Path:
    """Write a minimal curated-task dir under ``root`` and return its path."""
    task = root / "curated_task"
    (task / "tests" / "webdesign_rl_pkg" / "src" / "webdesign_rl").mkdir(
        parents=True
    )
    (task / "task.toml").write_text(_FIXTURE_TASK_TOML)
    # A stale module in the baked package that must NOT survive the refresh.
    (task / "tests" / "webdesign_rl_pkg" / "src" / "webdesign_rl"
     / "STALE_MODULE.py").write_text("# frozen at emit time\n")
    return task


def test_argv_builder_default_params_full_invocation():
    """The argv builder produces the full ``harbor run`` invocation for defaults."""
    argv = run_claude_code.build_harbor_argv(
        task_path="out/eval/004/task",
        job_name="opus47-004",
        api_key="sk-test",
    )

    assert argv[:2] == ["harbor", "run"]
    assert "-p" in argv
    assert argv[argv.index("-p") + 1] == "out/eval/004/task"
    # agent = claude-code, model = Opus 4.7 (the default).
    assert argv[argv.index("-a") + 1] == "claude-code"
    assert argv[argv.index("-m") + 1] == "claude-opus-4-7"
    # executor = modal (default), forced fresh build.
    assert argv[argv.index("-e") + 1] == "modal"
    assert "--force-build" in argv
    # attempts + concurrency default to 10/10.
    assert argv[argv.index("-k") + 1] == "10"
    assert argv[argv.index("-n") + 1] == "10"
    # job name.
    assert argv[argv.index("--job-name") + 1] == "opus47-004"


def test_argv_builder_wires_shared_key_to_agent_and_verifier():
    """The one shared key drives both the agent (--ae) and the verifier (--ve)."""
    argv = run_claude_code.build_harbor_argv(
        task_path="out/eval/004/task",
        job_name="opus47-004",
        api_key="sk-shared",
    )

    assert argv[argv.index("--ae") + 1] == "ANTHROPIC_API_KEY=sk-shared"
    assert argv[argv.index("--ve") + 1] == "ANTHROPIC_API_KEY=sk-shared"


def test_argv_builder_interactive_by_default_unattended_passthrough():
    """``--yes`` appears only when ``unattended`` is set; default is interactive."""
    interactive = run_claude_code.build_harbor_argv(
        task_path="t", job_name="j", api_key="k",
    )
    assert "--yes" not in interactive

    unattended = run_claude_code.build_harbor_argv(
        task_path="t", job_name="j", api_key="k", unattended=True,
    )
    assert "--yes" in unattended


def test_argv_builder_honors_overridden_params():
    """Non-default attempts / concurrency / model / executor pass through."""
    argv = run_claude_code.build_harbor_argv(
        task_path="t", job_name="j", api_key="k",
        attempts=3, concurrency=2, model="claude-sonnet-4-7", executor="docker",
    )
    assert argv[argv.index("-k") + 1] == "3"
    assert argv[argv.index("-n") + 1] == "2"
    assert argv[argv.index("-m") + 1] == "claude-sonnet-4-7"
    assert argv[argv.index("-e") + 1] == "docker"


def test_prepare_eval_copy_flips_agent_internet_only(tmp_path):
    """The eval copy flips the AGENT env online; the VERIFIER env is untouched."""
    source = _make_fixture_task(tmp_path)
    dest = tmp_path / "eval_copy"

    eval_copy = run_claude_code.prepare_eval_copy(source, dest)

    data = tomllib.loads((eval_copy / "task.toml").read_text())
    assert data["environment"]["allow_internet"] is True
    # The verifier env is left exactly as emitted (still online for the judge).
    assert data["verifier"]["environment"]["allow_internet"] is True
    # The source curated task is never mutated.
    src_data = tomllib.loads((source / "task.toml").read_text())
    assert src_data["environment"]["allow_internet"] is False


def test_module_is_import_safe_without_harbor_or_modal():
    """The module imports with neither Harbor nor Modal installed at module top."""
    import sys

    # Neither dependency is imported eagerly — the subprocess shell loads them
    # lazily, so the pure core is usable in a bare environment.
    assert "harbor" not in sys.modules
    assert "modal" not in sys.modules
    # The pure cores are reachable as attributes (no import-time side effects).
    assert callable(run_claude_code.build_harbor_argv)
    assert callable(run_claude_code.prepare_eval_copy)


def test_prepare_eval_copy_is_distinct_from_source(tmp_path):
    """The eval copy is a separate directory tree, not the source itself."""
    source = _make_fixture_task(tmp_path)
    dest = tmp_path / "eval_copy"

    eval_copy = run_claude_code.prepare_eval_copy(source, dest)

    assert eval_copy.resolve() == dest.resolve()
    assert eval_copy.resolve() != source.resolve()
    assert (eval_copy / "task.toml").exists()


def test_prepare_eval_copy_refreshes_baked_package_no_stale_leftovers(tmp_path):
    """The baked package is replaced with current source; stale modules gone."""
    source = _make_fixture_task(tmp_path)
    dest = tmp_path / "eval_copy"

    eval_copy = run_claude_code.prepare_eval_copy(source, dest)

    pkg = eval_copy / "tests" / "webdesign_rl_pkg" / "src" / "webdesign_rl"
    # The stale frozen module was cleared (no leftover from the old snapshot).
    assert not (pkg / "STALE_MODULE.py").exists()
    # Current repo source is present (real package modules baked in).
    assert (pkg / "__init__.py").exists()
    assert (pkg / "eval" / "run_claude_code.py").exists()
    # pyproject travels with the package so the verifier image can pip-install it.
    assert (eval_copy / "tests" / "webdesign_rl_pkg" / "pyproject.toml").exists()


def test_prepare_eval_copy_does_not_mutate_source(tmp_path):
    """A full prep leaves the source task byte-for-byte unchanged."""
    source = _make_fixture_task(tmp_path)
    before = (source / "task.toml").read_text()
    stale = (source / "tests" / "webdesign_rl_pkg" / "src" / "webdesign_rl"
             / "STALE_MODULE.py").read_text()

    run_claude_code.prepare_eval_copy(source, tmp_path / "eval_copy")

    assert (source / "task.toml").read_text() == before
    # The source's frozen package is untouched (refresh happened on the copy).
    assert (source / "tests" / "webdesign_rl_pkg" / "src" / "webdesign_rl"
            / "STALE_MODULE.py").read_text() == stale
