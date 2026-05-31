"""Text templates for the emitted Harbor task files.

Each function returns the exact contents of one task file. They are plain Python
string builders (not Jinja) because the substitutions are trivial and keeping the
shell/Dockerfile text literal makes it auditable. The Modal-portability
constraints are baked in here: a **plain Dockerfile** (no docker-compose), a
**self-contained** verifier image (Python + our package + Playwright + the
Chromium binary + Tesseract + a bundled font set), and pinned resources in
``task.toml``.
"""

from ..generate import fonts

# Where the agent publishes its produced site, and Harbor auto-transfers it to
# the separate verifier at the identical path. Both the instruction and the
# verifier entrypoint reference this single path.
ARTIFACTS_DIR = "/logs/artifacts"

# The reference screenshots the agent replicates. ``build_task`` renders one PNG
# per page into ``environment/<REFERENCE_DIRNAME>/`` (the agent-env build
# context); the agent Dockerfile COPYs that dir to ``AGENT_REFERENCE_DIR`` inside
# the container, and ``instruction.md`` points the agent at those paths.
REFERENCE_DIRNAME = "reference"
AGENT_REFERENCE_DIR = f"/app/{REFERENCE_DIRNAME}"


def instruction_md(page_map: dict, viewport: int) -> str:
    """The agent-facing instruction: screenshot -> output-file table + viewport.

    Screenshots-only: the agent is told to replicate each reference screenshot in
    HTML/CSS and never sees the reference source. The screenshots themselves are
    provided as PNG files under ``AGENT_REFERENCE_DIR`` (placed there by
    ``build_task`` + the agent Dockerfile); the table points at those paths. The
    agent writes its files into the publish directory so the (hidden) grader can
    render and score them.
    """
    rows = "\n".join(
        f"| `{AGENT_REFERENCE_DIR}/{spec['screenshot']}` | `{spec['expected_file']}` |"
        for spec in page_map.values()
    )
    return f"""\
# Replicate the web design

You are given reference **screenshots** of a {len(page_map)}-page website. Recreate
each page as faithfully as possible using **plain HTML and CSS**, matching the
layout, colors, typography, and text content you see in each screenshot.

You only have the screenshots — there is no reference source to copy. The reference
screenshots are PNG files in **`{AGENT_REFERENCE_DIR}/`**; open them to see what to
build. Your work is graded on how closely your *rendered* pages match these
reference screenshots.

## Rendering

Your pages are rendered headlessly at a fixed **viewport width of {viewport}px**
(full scroll height), offline. Use local/inline assets and CSS; external network
requests are blocked during rendering, so do not rely on CDNs or web fonts.

## Pages to produce

Write each output file listed below. The grader renders the file named in the
right column and compares it to the screenshot in the left column.

| Reference screenshot | Output file |
| --- | --- |
{rows}

## Where to write your files

Write all of your HTML/CSS/asset files into **`{ARTIFACTS_DIR}/`** (create it if
needed). Keep every page's relative asset paths working from that directory. Only
files under `{ARTIFACTS_DIR}/` are collected and graded.
"""


def task_toml(*, task_name: str, cpus: int, memory_mb: int) -> str:
    """``task.toml`` declaring a separate verifier env with pinned resources.

    The agent environment stays minimal and has no internet. The verifier runs in
    a *separate* environment (``[verifier.environment]`` ⇒ separate mode) built
    from ``tests/Dockerfile``; it gets ``allow_internet = true`` and the
    ``ANTHROPIC_API_KEY`` so the ``design_judge`` term can reach the API, while
    the deterministic-only mode needs neither. Resources are pinned because cloud
    backends enforce them.
    """
    return f"""\
schema_version = "1.2"

[task]
name = "{task_name}"
description = "Replicate a multi-page web design from reference screenshots."

[agent]
timeout_sec = 1800.0

[environment]
# The agent environment: minimal, offline. The agent writes its HTML here and
# publishes it to /logs/artifacts/ for the separate verifier.
allow_internet = false
cpus = {cpus}
memory_mb = {memory_mb}

[verifier]
timeout_sec = 1200.0
# A separate verifier environment hides the grading code, reference screenshots,
# and page_map from the agent. Built from tests/Dockerfile (tests/ is the build
# context); the image provides /tests/test.sh itself.
environment_mode = "separate"

[verifier.environment]
allow_internet = true
cpus = {cpus}
memory_mb = {memory_mb}

[verifier.env]
# Used by the live design_judge term, which test.sh runs by default. (Drop
# --no-judge back into test.sh for deterministic-only grading, which ignores it.)
ANTHROPIC_API_KEY = "${{ANTHROPIC_API_KEY}}"
"""


def agent_dockerfile() -> str:
    """The agent environment image: minimal, with a writable workspace.

    Plain Dockerfile (Modal-portable). The agent authors files here and gets the
    reference screenshots to replicate baked in at ``AGENT_REFERENCE_DIR``;
    rendering/grading happens in the separate verifier image. ``environment/`` is
    the build context, so ``COPY {REFERENCE_DIRNAME}`` picks up the PNGs that
    ``build_task`` rendered into ``environment/{REFERENCE_DIRNAME}/``.
    """
    return f"""\
FROM ubuntu:24.04

# A working directory for the agent to author its HTML/CSS in. The agent
# publishes its finished site to /logs/artifacts/ (see instruction.md).
WORKDIR /app
RUN mkdir -p /logs/artifacts

# The reference screenshots to replicate (one PNG per page), rendered at emit
# time into the agent-env build context. instruction.md points the agent here.
COPY {REFERENCE_DIRNAME} {AGENT_REFERENCE_DIR}
"""


def verifier_dockerfile() -> str:
    """The self-contained verifier image (Modal-portable, plain Dockerfile).

    Bakes in *everything* the grader needs so the task runs identically locally
    (``--env docker``) and on cloud sandboxes (``--env modal``): Python, our
    package, Playwright **and the Chromium binary**, Tesseract, the curated font
    palette installed OS-level (+ DejaVu fallback) for deterministic *faithful*
    rendering, the grader code, the reference screenshots, and ``page_map`` —
    plus ``/tests/test.sh``.
    """
    return f"""\
FROM python:3.14-slim

# System deps: Tesseract (content/OCR term) + the DejaVu fallback font set
# (every palette family degrades to it identically) + curl (build-time palette
# fetch), plus the libraries headless Chromium needs.
RUN apt-get update && apt-get install -y --no-install-recommends \\
        tesseract-ocr \\
        fonts-dejavu-core \\
        fontconfig \\
        ca-certificates \\
        curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && fc-cache -f

{fonts.dockerfile_install_block()}

# Browser-engine layer FIRST, before the package + per-task COPYs. Chromium and
# its OS deps (--with-deps) are large and source-INDEPENDENT, so placing them
# ahead of the COPYs means a package or per-task change busts only the cheap
# layers below rather than re-baking Chromium. playwright is a core dep
# (>=1.49), so installing it here leaves it satisfied by the package install
# below — the engine matches this baked Chromium (no version/binary drift).
RUN pip install --no-cache-dir "playwright>=1.49" \\
    && playwright install --with-deps chromium

# Our package + its dependencies (Playwright is a core dep as of issue 05).
COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]

# Where task_builder re-stages the package from when emitting inside an image
# (parity with the render image; harmless here since the verifier never emits).
ENV WEBDESIGN_RL_PKG_ROOT=/opt/webdesign_rl_pkg

# Bake the grader inputs hidden from the agent: the reference HTML site (rendered
# in-container at grade time with the same engine/fonts as the candidate, so the
# ceiling is exact and host-independent) + page_map.
COPY reference_site /tests/reference_site
COPY page_map.json /tests/page_map.json

# The verifier entrypoint. For a separate verifier env Harbor does NOT upload
# tests/, so the image must provide /tests/test.sh itself.
COPY test.sh /tests/test.sh
RUN chmod +x /tests/test.sh
"""


def test_sh() -> str:
    """The verifier entrypoint: render the agent's site, grade, write reward.json.

    Reads the agent's published HTML from ``/logs/artifacts/`` (auto-transferred
    from the agent env), renders the baked reference HTML in the *same* container,
    and grades with the grader CLI in the **full 4-term mode** (including the live
    ``design_judge`` term), writing ``/logs/verifier/reward.json``. The judge
    needs the verifier's ANTHROPIC_API_KEY + allow_internet (both wired in
    ``task.toml``); add ``--no-judge`` to fall back to deterministic-only grading
    (three terms, no key/egress) for an offline or zero-cost run.
    """
    return f"""\
#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python -m webdesign_rl.grade \\
    --candidate {ARTIFACTS_DIR} \\
    --reference-site /tests/reference_site \\
    --page-map /tests/page_map.json \\
    --out /logs/verifier
"""
