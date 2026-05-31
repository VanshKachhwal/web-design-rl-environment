"""Behavioral tests for the pull_artifacts CLI's pure core (issue 26).

``pull_artifacts.py`` downloads a Modal volume into a local dir — the command form
of ``modal volume get webdesign-rl-artifacts / out/batch``. Same split as the eval
launcher / ``modal_batch``: the ``subprocess``/``modal`` invocation is an untested,
thin shell; the pure **argv builder** that decides *what* runs is unit-tested here,
with no Modal / network / subprocess.

We assert external behavior: the exact ``modal volume get`` argv list (incl. flag
order) for the default / ``--force`` / ``--env`` / both / custom-dest cases, and
that the builder ``str()``s a ``Path`` dest. The builder must be importable without
``modal`` installed (the script is import-safe).
"""

import sys
from pathlib import Path

# scripts/ is not a package; import build_pull_argv by adding it to the path, the
# same convention scripts/report_all.py uses for its sibling imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from pull_artifacts import build_pull_argv  # noqa: E402


def test_default_argv_is_plain_volume_get():
    assert build_pull_argv("webdesign-rl-artifacts", "out/batch") == [
        "modal", "volume", "get", "webdesign-rl-artifacts", "/", "out/batch",
    ]


def test_force_appends_force_flag():
    assert build_pull_argv("vol", "dest", force=True) == [
        "modal", "volume", "get", "vol", "/", "dest", "--force",
    ]


def test_env_appends_dash_e_and_value():
    assert build_pull_argv("vol", "dest", env="prod") == [
        "modal", "volume", "get", "vol", "/", "dest", "-e", "prod",
    ]


def test_force_and_env_both_appended_force_before_env():
    assert build_pull_argv("vol", "dest", force=True, env="prod") == [
        "modal", "volume", "get", "vol", "/", "dest", "--force", "-e", "prod",
    ]


def test_path_dest_is_stringified():
    assert build_pull_argv("vol", Path("out") / "batch-a") == [
        "modal", "volume", "get", "vol", "/", str(Path("out") / "batch-a"),
    ]
