"""Assemble a runnable Harbor task directory from a reference site + ``page_map``.

:func:`build_task` is the packager: hand it the **ground-truth** site directory
(the reference HTML/CSS) and a ``page_map`` and it writes a complete Harbor task
directory whose grader runs in a **separate verifier environment** — the grading
code, the reference screenshots, and the ``page_map`` are baked into the verifier
image and never exposed to the agent.

Layout produced (see ``docs/harbor/links.md`` → Task Structure for the mechanics)::

    out_task_dir/
    ├── instruction.md        # screenshot -> output-filename table + viewport
    ├── task.toml             # separate [verifier.environment], pinned cpus/memory,
    │                         #   allow_internet + ANTHROPIC_API_KEY on the verifier
    ├── environment/          # === the *agent* env build context ===
    │   ├── Dockerfile        # minimal; agent writes HTML here, COPYs reference/ in
    │   └── reference/        # rendered reference PNGs the agent replicates
    │                         #   (one per page; COPYed to /app/reference/)
    ├── solution/
    │   └── solve.sh          # the oracle: writes the reference site into the
    │                         #   agent's publish dir so the grader scores ~1.0
    └── tests/                # === the separate verifier's build context ===
        ├── Dockerfile        # self-contained verifier image: python + our package
        │                     #   + playwright(+chromium) + tesseract + fonts + grader
        │                     #   + reference PNGs + page_map; bakes /tests/test.sh
        ├── test.sh           # verifier entrypoint -> /logs/verifier/reward.json
        ├── page_map.json     # baked grader input
        ├── reference/        # baked reference screenshots (one PNG per page)
        └── webdesign_rl/     # baked copy of our package source + pyproject

**Agent-output → verifier transfer.** The agent writes its produced site into
``/logs/artifacts/`` (Harbor's per-agent *publish* directory). Harbor downloads
that directory and, because the verifier runs in a *separate* environment,
re-uploads it to the verifier's ``/logs/artifacts/`` at the identical path. The
verifier's ``test.sh`` therefore renders the agent's HTML from
``/logs/artifacts/`` and compares it to the baked reference. No ``artifacts =``
list is needed — ``/logs/artifacts/`` is the auto-transferred convention path.

**Why ``tests/`` is the verifier build context.** For a separate verifier Harbor
does *not* upload ``tests/`` at runtime; instead it builds the verifier image
from ``tests/Dockerfile`` (with ``tests/`` as the build context) and the image
must provide ``/tests/test.sh`` itself. So everything the grader needs is copied
under ``tests/`` and ``COPY``-ed into the image.
"""

import json
import shutil
from pathlib import Path

from ..render.browser import render_site
from . import oracle, templates

# Repo root that holds ``pyproject.toml`` and ``src/webdesign_rl`` — derived from
# this file's location so packaging works without an editable install (the
# project runs via ``pythonpath=["src"]``, so the package is never pip-installed).
_PACKAGE_DIR = Path(__file__).resolve().parents[1]      # .../src/webdesign_rl
_REPO_ROOT = Path(__file__).resolve().parents[3]         # repo root
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# Default capture/viewport width (design decision: 1280px desktop, full height).
VIEWPORT = 1280

# Pinned verifier resources. Cloud backends (Modal/Daytona/...) enforce these, so
# they are explicit rather than "whatever the host has". Chromium + the renderer
# are memory-hungry, hence a generous default.
DEFAULT_CPUS = 2
DEFAULT_MEMORY_MB = 4096


def build_task(
    reference_site_dir,
    page_map,
    out_task_dir,
    *,
    task_name: str = "webdesign-rl/replicate-site",
    viewport: int = VIEWPORT,
    cpus: int = DEFAULT_CPUS,
    memory_mb: int = DEFAULT_MEMORY_MB,
):
    """Assemble a Harbor task directory from a reference site and ``page_map``.

    Args:
        reference_site_dir: the ground-truth site (HTML/CSS/assets). It is baked
            into the verifier image (rendered *there* at grade time, with the same
            engine/fonts as the candidate) and copied into ``solution/`` so the
            oracle can reproduce it exactly.
        page_map: ``{page: {"screenshot": "<png>", "expected_file": "<html>"}}``.
        out_task_dir: directory to create the Harbor task in.
        task_name: the ``[task].name`` (``org/name``) recorded in ``task.toml``.
        viewport: render/capture width in CSS px, stated in ``instruction.md``.
        cpus, memory_mb: pinned verifier-environment resources.

    Returns:
        The ``Path`` to the created task directory.
    """
    reference_site_dir = Path(reference_site_dir)
    out = Path(out_task_dir)

    tests_dir = out / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (out / "environment").mkdir(parents=True, exist_ok=True)
    (out / "solution").mkdir(parents=True, exist_ok=True)

    # Bake the reference HTML site into the verifier build context. The verifier
    # renders it at grade time with the same engine/fonts as the candidate, so an
    # identical candidate scores an exact ceiling (no committed-PNG host/container
    # font mismatch). The reference stays hidden from the agent (separate env).
    _copy_tree(reference_site_dir, tests_dir / "reference_site")

    # Bake the grader inputs into the verifier build context.
    (tests_dir / "page_map.json").write_text(json.dumps(page_map, indent=2))
    _copy_package(tests_dir / "webdesign_rl_pkg")

    # Write the task files from templates.
    (out / "instruction.md").write_text(
        templates.instruction_md(page_map, viewport)
    )
    (out / "task.toml").write_text(
        templates.task_toml(task_name=task_name, cpus=cpus, memory_mb=memory_mb)
    )
    (out / "environment" / "Dockerfile").write_text(templates.agent_dockerfile())

    # Render one reference screenshot per page into the agent-env build context so
    # the agent has something to replicate (the Dockerfile COPYs them into the
    # container at templates.AGENT_REFERENCE_DIR; instruction.md points there).
    # Host-rendered for now — making this font-consistent with grading is issue 09.
    _render_agent_screenshots(
        reference_site_dir,
        page_map,
        out / "environment" / templates.REFERENCE_DIRNAME,
        viewport,
    )
    (tests_dir / "Dockerfile").write_text(templates.verifier_dockerfile())
    (tests_dir / "test.sh").write_text(templates.test_sh())

    # The oracle solution: copy the reference site in and write solve.sh.
    oracle.write_solution(out / "solution", reference_site_dir, page_map)

    return out


def _render_agent_screenshots(
    reference_site_dir: Path, page_map: dict, dest: Path, viewport: int
) -> None:
    """Render the reference site to one PNG per page under ``dest``.

    These are the screenshots the *agent* replicates — distinct from grading,
    which re-renders the reference HTML in-container. ``dest`` lives in the
    agent-env build context, and each PNG is named by the page's ``screenshot``
    field so ``instruction.md``'s table paths line up.
    """
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    images = render_site(reference_site_dir, page_map, viewport=viewport)
    for page_name, spec in page_map.items():
        image = images.get(page_name)
        if image is None:
            # render_site omits a page whose expected_file is absent; such a
            # page_map is malformed for emit (the agent would have no reference).
            raise ValueError(
                f"reference site has no renderable page for '{page_name}' "
                f"(expected_file={spec.get('expected_file')!r})"
            )
        image.save(dest / spec["screenshot"])


def _copy_tree(src: Path, dest: Path) -> None:
    """Copy a directory tree into the task, replacing any existing destination."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )


def _copy_package(dest: Path) -> None:
    """Copy our package source + pyproject into the verifier build context.

    The verifier image is self-contained: it ``pip install``s this copied source,
    so the grader code travels *with* the task rather than relying on a registry
    or the host. ``__pycache__`` is excluded to keep the context lean.
    """
    _copy_tree(_PACKAGE_DIR, dest / "src" / "webdesign_rl")
    shutil.copy2(_PYPROJECT, dest / "pyproject.toml")
