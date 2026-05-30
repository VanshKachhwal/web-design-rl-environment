"""Text templates for the emitted Harbor task files.

Each function returns the exact contents of one task file. They are plain Python
string builders (not Jinja) because the substitutions are trivial and keeping the
shell/Dockerfile text literal makes it auditable. The Modal-portability
constraints are baked in here: a **plain Dockerfile** (no docker-compose), a
**self-contained** verifier image (Python + our package + Playwright + the
Chromium binary + Tesseract + a bundled font set), and pinned resources in
``task.toml``.
"""

# Where the agent publishes its produced site, and Harbor auto-transfers it to
# the separate verifier at the identical path. Both the instruction and the
# verifier entrypoint reference this single path.
ARTIFACTS_DIR = "/logs/artifacts"


def instruction_md(page_map: dict, viewport: int) -> str:
    """The agent-facing instruction: screenshot -> output-file table + viewport.

    Screenshots-only: the agent is told to replicate each reference screenshot in
    HTML/CSS and never sees the reference source. It writes its files into the
    publish directory so the (hidden) grader can render and score them.
    """
    rows = "\n".join(
        f"| `{spec['screenshot']}` | `{spec['expected_file']}` |"
        for spec in page_map.values()
    )
    return f"""\
# Replicate the web design

You are given reference **screenshots** of a {len(page_map)}-page website. Recreate
each page as faithfully as possible using **plain HTML and CSS**, matching the
layout, colors, typography, and text content you see in each screenshot.

You only have the screenshots — there is no reference source to copy. Your work is
graded on how closely your *rendered* pages match the reference screenshots.

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
# Needed only for the live design_judge term; the deterministic-only grading
# mode (test.sh default) ignores it.
ANTHROPIC_API_KEY = "${{ANTHROPIC_API_KEY}}"
"""


def agent_dockerfile() -> str:
    """The agent environment image: minimal, with a writable workspace.

    Plain Dockerfile (Modal-portable). The agent only needs a place to author
    files; rendering/grading happens in the separate verifier image.
    """
    return """\
FROM ubuntu:24.04

# A working directory for the agent to author its HTML/CSS in. The agent
# publishes its finished site to /logs/artifacts/ (see instruction.md).
WORKDIR /app
RUN mkdir -p /logs/artifacts
"""


def verifier_dockerfile() -> str:
    """The self-contained verifier image (Modal-portable, plain Dockerfile).

    Bakes in *everything* the grader needs so the task runs identically locally
    (``--env docker``) and on cloud sandboxes (``--env modal``): Python, our
    package, Playwright **and the Chromium binary**, Tesseract, a bundled font
    set referenced for deterministic rendering, the grader code, the reference
    screenshots, and ``page_map`` — plus ``/tests/test.sh``.
    """
    return """\
FROM python:3.12-slim

# System deps: Tesseract (content/OCR term) + a deterministic bundled font set
# (DejaVu) so rendering does not depend on host fonts, plus the libraries
# headless Chromium needs.
RUN apt-get update && apt-get install -y --no-install-recommends \\
        tesseract-ocr \\
        fonts-dejavu-core \\
        fontconfig \\
        ca-certificates \\
    && rm -rf /var/lib/apt/lists/* \\
    && fc-cache -f

# Our package + its dependencies (Playwright moved to core deps in issue 05).
COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]

# Bake the Chromium binary into the image (no download at grade time) and its
# OS dependencies.
RUN playwright install --with-deps chromium

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
    and grades with the grader CLI in **deterministic-only mode** (``--no-judge``
    — robust, no key/egress), writing ``/logs/verifier/reward.json``. Swap
    ``--no-judge`` out (and keep the verifier's ANTHROPIC_API_KEY + allow_internet)
    to enable the live judge.
    """
    return f"""\
#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python -m webdesign_rl.grade \\
    --candidate {ARTIFACTS_DIR} \\
    --reference-site /tests/reference_site \\
    --page-map /tests/page_map.json \\
    --out /logs/verifier \\
    --no-judge
"""
