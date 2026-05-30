"""Write the oracle solution: reproduce the ground-truth site for the agent.

The Harbor oracle agent copies ``solution/`` to ``/solution`` in the agent
container and runs ``solve.sh``. To validate the packaged grader's *ceiling*, the
oracle must produce exactly the reference site, so the grader scores ~1.0.

We do this the robust way: bundle the reference site's files into
``solution/site/`` and have ``solve.sh`` copy them verbatim into the agent's
publish directory (``/logs/artifacts/``). Because the verifier renders that same
HTML with the same module the reference PNGs were rendered from, the candidate
and reference renders are pixel-identical — the deterministic terms hit ~1.0.
"""

import shutil
from pathlib import Path

# Single source of truth for the agent publish directory the verifier reads from.
from .templates import ARTIFACTS_DIR as _ARTIFACTS_DIR


def write_solution(solution_dir, reference_site_dir, page_map) -> None:
    """Populate ``solution/`` with the bundled reference site and ``solve.sh``.

    Args:
        solution_dir: the task's ``solution/`` directory to write into.
        reference_site_dir: the ground-truth site to bundle and reproduce.
        page_map: the page map (used to sanity-check the required HTML files are
            present in the reference site).
    """
    solution_dir = Path(solution_dir)
    reference_site_dir = Path(reference_site_dir)

    # Bundle the reference site under solution/site/ so solve.sh can copy it.
    site_dest = solution_dir / "site"
    if site_dest.exists():
        shutil.rmtree(site_dest)
    shutil.copytree(
        reference_site_dir,
        site_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    (solution_dir / "solve.sh").write_text(_solve_sh())


def _solve_sh() -> str:
    """The oracle script: publish the bundled reference site to /logs/artifacts/.

    Runs in the agent container (cwd ``/app``); the bundle lives at
    ``/solution/site``. Copying it verbatim into ``/logs/artifacts/`` means the
    oracle's output *is* the reference site, so the grader's ceiling is exercised.
    """
    return f"""\
#!/bin/bash
set -euo pipefail

mkdir -p {_ARTIFACTS_DIR}
cp -r /solution/site/. {_ARTIFACTS_DIR}/
"""
