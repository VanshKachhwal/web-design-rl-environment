"""Package the animated reference into a runnable Harbor task (Part 2).

Mirrors Task 1's ``emit/task_builder.py`` + ``emit/templates.py`` (kept separate so
Task 1 is untouched), with the animation-specific differences:

* the **agent** is given a *filmstrip* — one PNG per timestamp plus a single
  captioned contact sheet — instead of one screenshot per page, and is told to
  reproduce the **animation** (CSS-only) as well as the static design;
* the **verifier** bakes BOTH packages (Task 1's ``webdesign_rl`` for the reused
  static metrics/judge, and this ``webdesign_rl_anim``) and runs the animation
  grader (``grade_anim``) → ``/logs/verifier/reward.json``.

Output layout is the Task-1 shape (``environment/`` = agent build context,
``tests/`` = separate-verifier build context, ``solution/solve.sh`` = oracle).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from .filmstrip import contact_sheet
from .render_anim import DEFAULT_TIMESTAMPS_MS, render_filmstrip

_REPO_ROOT = Path(__file__).resolve().parents[2]
_T1_PKG = _REPO_ROOT / "src" / "webdesign_rl"
_T1_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_T2_PKG = _REPO_ROOT / "task2" / "webdesign_rl_anim"

VIEWPORT = 1280
REFERENCE_DIRNAME = "reference"
AGENT_REFERENCE_DIR = f"/app/{REFERENCE_DIRNAME}"
ARTIFACTS_DIR = "/logs/artifacts"


def build_anim_task(
    reference_site_dir,
    out_task_dir,
    *,
    task_name: str = "webdesign-rl-anim/replicate-animated-site",
    timestamps_ms=DEFAULT_TIMESTAMPS_MS,
    viewport: int = VIEWPORT,
    cpus: int = 2,
    memory_mb: int = 4096,
):
    """Assemble the Harbor task directory for the animated reference site."""
    reference_site_dir = Path(reference_site_dir)
    out = Path(out_task_dir)
    tests = out / "tests"
    env = out / "environment"
    sol = out / "solution"
    for d in (tests, env, sol):
        d.mkdir(parents=True, exist_ok=True)

    page_map = {"index": {"expected_file": "index.html", "screenshot": "index.png"}}
    timestamps = list(timestamps_ms)

    # --- verifier build context: reference site (hidden), page_map, both packages
    _copy_tree(reference_site_dir, tests / "reference_site")
    (tests / "page_map.json").write_text(json.dumps(page_map, indent=2))
    _copy_tree(_T1_PKG, tests / "webdesign_rl_pkg" / "src" / "webdesign_rl")
    shutil.copy2(_T1_PYPROJECT, tests / "webdesign_rl_pkg" / "pyproject.toml")
    _copy_tree(_T2_PKG, tests / "webdesign_rl_anim_pkg" / "webdesign_rl_anim")
    (tests / "Dockerfile").write_text(_verifier_dockerfile())
    (tests / "test.sh").write_text(_test_sh())

    # --- agent build context: the filmstrip the agent must reproduce
    _render_agent_filmstrip(reference_site_dir, env / REFERENCE_DIRNAME,
                            timestamps, viewport)
    (out / "instruction.md").write_text(_instruction_md(timestamps, viewport))
    (out / "task.toml").write_text(_task_toml(task_name, cpus, memory_mb))
    (env / "Dockerfile").write_text(_agent_dockerfile())

    # --- oracle solution: the reference page itself scores ~1.0
    (sol / "site").mkdir(parents=True, exist_ok=True)
    shutil.copy2(reference_site_dir / "index.html", sol / "site" / "index.html")
    (sol / "solve.sh").write_text(_solve_sh())
    return out


def _render_agent_filmstrip(reference_site_dir, dest, timestamps, viewport):
    """Render the reference filmstrip frames + contact sheet into the agent context."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    r = render_filmstrip(reference_site_dir, "index.html", timestamps, viewport=viewport)
    for t, frame in zip(r["timestamps_ms"], r["frames"]):
        frame.save(dest / f"index_t{t:05d}.png")
    contact_sheet(r["frames"], r["timestamps_ms"]).save(dest / "index_filmstrip.png")
    r["settled"].save(dest / "index_settled.png")


def _copy_tree(src, dest):
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


# ----------------------------------------------------------------------------- templates

def _instruction_md(timestamps, viewport) -> str:
    frame_rows = "\n".join(
        f"| `{AGENT_REFERENCE_DIR}/index_t{t:05d}.png` | {t} ms |"
        for t in timestamps
    )
    return f"""\
# Replicate the animated web design

You are given a reference **animated** landing page as a *filmstrip*: full-page
screenshots captured at increasing times after the page loads, plus a single
stacked **contact sheet** (`{AGENT_REFERENCE_DIR}/index_filmstrip.png`) and the
final at-rest frame (`{AGENT_REFERENCE_DIR}/index_settled.png`). Recreate the page
as a single **`index.html`** using **plain HTML and CSS only**, matching both the
**static design** (layout, colors, typography, text) *and* the **animation** (what
moves, when, the easing/feel, and the kind of motion).

## The filmstrip (absolute times on the page timeline)

| Reference frame | Captured at |
| --- | --- |
{frame_rows}

Study how elements enter, stagger, and loop across these frames. Your page is
captured at the **same absolute times** and graded on how closely each frame — and
the motion between them — matches.

## Animation rules (important)

- Use **CSS only**: `@keyframes` animations and CSS transitions. **No JavaScript**,
  no `<script>`, no `requestAnimationFrame` — the grader seeks the CSS timeline and
  will not see JS-driven motion.
- Give finite entrance/stagger animations `animation-fill-mode: forwards` so the
  page holds its final state at rest (the settled frame is graded for static design).
- Match the **timing**: entrance + stagger should play within the same window you
  see in the filmstrip; reproduce any continuous (infinite) loops you observe.

## Rendering

Rendered headlessly at a fixed **viewport width of {viewport}px** (full scroll
height), **offline** — inline all CSS, use system fonts and CSS-drawn shapes/
gradients, no CDNs or web fonts.

## Where to write your file

Write your **`index.html`** (with all CSS inline) into **`{ARTIFACTS_DIR}/`** (create
it if needed). Only files under `{ARTIFACTS_DIR}/` are collected and graded.
"""


def _task_toml(task_name, cpus, memory_mb) -> str:
    return f"""\
schema_version = "1.2"

[task]
name = "{task_name}"
description = "Replicate a multi-page animated web design from a reference filmstrip."

[agent]
timeout_sec = 1800.0

[environment]
allow_internet = false
cpus = {cpus}
memory_mb = {memory_mb}

[verifier]
timeout_sec = 1800.0
environment_mode = "separate"

[verifier.environment]
allow_internet = true
cpus = {cpus}
memory_mb = {memory_mb}

[verifier.env]
# Used by the live design_judge + animation_judge terms (full mode). Add
# --no-judge in test.sh for deterministic-only grading (no key/egress).
ANTHROPIC_API_KEY = "${{ANTHROPIC_API_KEY}}"
"""


def _agent_dockerfile() -> str:
    return f"""\
FROM ubuntu:24.04
WORKDIR /app
RUN mkdir -p /logs/artifacts
# The reference filmstrip (frames + contact sheet) the agent must reproduce.
COPY {REFERENCE_DIRNAME} {AGENT_REFERENCE_DIR}
"""


def _verifier_dockerfile() -> str:
    from webdesign_rl.generate import fonts  # read-only reuse of Task 1's font block

    return f"""\
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        tesseract-ocr \\
        fonts-dejavu-core \\
        fontconfig \\
        ca-certificates \\
        curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && fc-cache -f

{fonts.dockerfile_install_block()}

# Browser engine first (large, source-independent layer).
RUN pip install --no-cache-dir "playwright>=1.49" \\
    && playwright install --with-deps chromium

# Task 1 package (reused static metrics + judge) with the grade extra.
COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]
ENV WEBDESIGN_RL_PKG_ROOT=/opt/webdesign_rl_pkg

# Task 2 animation package, on PYTHONPATH (pure-python; deps satisfied above).
COPY webdesign_rl_anim_pkg /opt/webdesign_rl_anim_pkg
ENV PYTHONPATH=/opt/webdesign_rl_anim_pkg

# Baked, hidden-from-agent grader inputs.
COPY reference_site /tests/reference_site
COPY page_map.json /tests/page_map.json

COPY test.sh /tests/test.sh
RUN chmod +x /tests/test.sh
"""


def _test_sh() -> str:
    return f"""\
#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

python -m webdesign_rl_anim.grade_anim \\
    --candidate {ARTIFACTS_DIR} \\
    --reference-site /tests/reference_site \\
    --page-map /tests/page_map.json \\
    --out /logs/verifier
"""


def _solve_sh() -> str:
    return f"""\
#!/bin/bash
set -euo pipefail
mkdir -p {ARTIFACTS_DIR}
cp /solution/site/index.html {ARTIFACTS_DIR}/index.html
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.emit_anim",
        description="Package an animated reference site into a Harbor task.",
    )
    parser.add_argument("--reference-site", required=True)
    parser.add_argument("--out", required=True, help="Output task directory.")
    parser.add_argument("--task-name", default="webdesign-rl-anim/replicate-animated-site")
    args = parser.parse_args(argv)

    out = build_anim_task(args.reference_site, args.out, task_name=args.task_name)
    print(f"built Harbor task at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
