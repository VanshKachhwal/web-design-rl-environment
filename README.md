# Web-Design Replication RL Environment

A scalable pipeline that **generates** multi-page web-design tasks from scratch and
**grades** a coding agent's attempt to replicate them from screenshots alone — built
on the **Harbor** RL-environment framework, evaluated with Claude Code + Opus 4.7.
Functionality is out of scope by design; the reward measures the *visual + content
fidelity* of the replication.

This repo is built around one conviction the brief makes explicit — *the model learns
the grading logic, so a noisy reward poisons training.* So the grader came first, and
its validity is **proven, not asserted**. Start there:

---

## The reward is a faithful signal — here's the proof

We manufacture variants of a reference site whose quality ordering is *known a priori*
(controlled perturbations at rising severity), score them with the real grader, and
check the reward respects that ordering. It does — **monotonically, on every axis**:

![reward vs perturbation severity](reports/grader-validation/reward_vs_severity.png)

- **Spearman ρ = −1.000**, pairwise-ordering accuracy **1.00** — reward falls
  monotonically as damage rises (`0.998 → 0.925 → 0.851 → 0.790 → 0.672 → 0.377`).
- **Oracle (reference vs itself) = 0.996** vs **Opus 4.7 ≈ 0.76** — a large, healthy
  gap, so the grader genuinely discriminates quality rather than saturating.
- Each of the four terms responds to *its own* perturbation axis; degenerate outputs
  (blank / gray / lorem) are floored by the blend.

→ **Full study with all four curves: [`reports/grader-validation/`](reports/grader-validation/)**
(renders inline on GitHub; every number is auditable in its `scores.json`).

---

## Results — Claude Code + Opus 4.7, 10× per task

Under that validated reward, across all 11 final tasks (per-term means, sorted by reward):

| task | type | pages | reward | structure | color | content | design_judge | report |
|---|---|---|---|---|---|---|---|---|
| 011 | ecommerce-store · brutalist | 10 | **0.660** ⬇ | 0.48 | 0.96 | 0.53 | 0.68 | [report](tasks/011_ecommerce-store_brutalist_high/report.md) |
| 007 | event-conference · retro-y2k | 7 | **0.727** | 0.76 | 0.94 | 0.60 | 0.64 | [report](tasks/007_event-conference_retro-y2k_med/report.md) |
| 035 | local-service · dark-techy | 10 | **0.739** | 0.74 | 0.98 | 0.54 | 0.69 | [report](tasks/035_local-service_dark-techy_high/report.md) |
| 038 | agency-portfolio · luxury-serif | 10 | **0.743** | 0.71 | 0.98 | 0.54 | 0.73 | [report](tasks/038_agency-portfolio_luxury-serif_high/report.md) |
| 012 | restaurant-hospitality · neo-brutalist | 5 | **0.775** | 0.72 | 0.96 | 0.69 | 0.71 | [report](tasks/012_restaurant-hospitality_neo-brutalist_low/report.md) |
| 023 | nonprofit-civic · glassmorphism | 10 | **0.781** | 0.82 | 0.98 | 0.66 | 0.68 | [report](tasks/023_nonprofit-civic_glassmorphism_high/report.md) |
| 004 | editorial-blog · corporate-flat | 7 | **0.787** | 0.79 | 0.97 | 0.67 | 0.73 | [report](tasks/004_editorial-blog_corporate-flat_med/report.md) |
| 036 | docs-product · warm-organic | 5 | **0.792** | 0.77 | 0.96 | 0.69 | 0.74 | [report](tasks/036_docs-product_warm-organic_low/report.md) |
| 019 | saas-landing · playful-rounded | 7 | **0.793** | 0.79 | 0.98 | 0.69 | 0.69 | [report](tasks/019_saas-landing_playful-rounded_med/report.md) |
| 015 | personal-resume · dark-techy | 5 | **0.798** | 0.77 | 0.96 | 0.71 | 0.74 | [report](tasks/015_personal-resume_dark-techy_low/report.md) |
| 000 | saas-landing · swiss-editorial | 5 | **0.827** ⬆ | 0.78 | 0.99 | 0.77 | 0.77 | [report](tasks/000_saas-landing_swiss-editorial_low/report.md) |

Per-task distributions, per-page heatmaps, and reference-vs-candidate galleries are in
each [`tasks/<id>/report.md`](tasks/).

---

## Key Learnings

The grader produces a real spread (**0.66 → 0.83**), and the *same shape every time*:

- **`content` is the bottleneck.** `color` is near-ceiling (mean **0.97**) while
  **`content` is the lowest term on every single task** (mean **0.65**).
- **`structure` is the next limiter** (mean ~0.74). The model reproduces the page
  architecture faithfully — sections, order, components — but loses points on **vertical
  rhythm and section-level treatment** (clearest in `011`, which compresses the layout and
  inverts several section backgrounds dark↔light). MS-SSIM is deliberately strict about
  pixel alignment, so a faithful-but-not-identical rebuild sits well below the same-code
  oracle's ≈1.0 — structure's practical ceiling is lower than color's by design.
- **Typography (fonts) is a related, qualitative contributor.** The agent is told to use
  system fonts but not *which*, so its typeface and weight choices diverge from the
  reference — shifting text glyphs out of alignment (so it surfaces in `structure` via
  MS-SSIM) and softening the overall look (so the `design_judge` notices it too). We
  *observe* this rather than score it as a separate term; it is part of the structure/look
  gap, not a distinct metric.

**The headline learning:** `content` is the bottleneck, and its fidelity is **inversely
proportional to prose density** — the model paraphrases body copy (generation is its
native mode, not transcription) while nailing layout and color. Cross-confirmed by the
OCR term *and* the VLM judge. This is exactly the "what the model struggles with"
finding the brief asks for; the design-taste tension (is verbatim text the right thing
to reward in a *design* task?) is surfaced, not hidden.

---

## What the brief asked, and where it lives

| Brief deliverable / requirement | Where in this repo |
|---|---|
| Recipe code — the generation + grading pipeline | [`src/webdesign_rl/`](src/webdesign_rl/) (`generate/`, `grade/`, `render/`, `emit/`, `eval/`) + [`scripts/`](scripts/) |
| Documentation of **how the problem was thought through** | [`documentation/`](documentation/) — start at [`index.md`](documentation/index.md) |
| **≥10 final tasks** showcasing distribution + complexity | [`tasks/`](tasks/) — **11 tasks**, see [`tasks/README.md`](tasks/README.md) |
| **Visual report of results** (Opus 4.7 ×10, how the grader scores) | each [`tasks/<id>/report.md`](tasks/) — renders on GitHub |
| **Why higher reward = better replication** | [`reports/grader-validation/`](reports/grader-validation/) (the proof above) + the per-task galleries |
| **Patterns the model struggles with** | [`documentation/design/eval_pipeline.md`](documentation/design/eval_pipeline.md) (the `content` finding) |
| Continuous (not pass/fail) grading | 4-term reward ∈ [0,1] — [`documentation/design/grader_design.md`](documentation/design/grader_design.md) |
| Generated from scratch (no crawling); ≥5 pages; design-only | [`documentation/design/generator_design.md`](documentation/design/generator_design.md) (taxonomy, 5–10 pages, static-only gate) |
| **Part 2 — animations** (attempted; rushed prototype, *not* in the final tasks) | writeup → [`task2/`](task2/README.md) (filmstrip grader + two-pass generator + scaling pipeline) · **10 preliminary tasks + 10× Opus-4.7 reports** → [`task2/tasks/`](task2/tasks/) |
| **Part 3 — multiple frameworks** (React/Solid/Tailwind) | *Not built* — designed-for in the architecture, deferred |

The assignment we built against is preserved verbatim at
[`documentation/project-brief.md`](documentation/project-brief.md).

---

## The final tasks

[`tasks/`](tasks/) holds **11 self-contained bundles** chosen to span the output
distribution — **all 10 archetypes × all 10 aesthetics**, complexity at **5 / 7 / 10
pages**, and the **full observed score range 0.66 → 0.827** (both extremes included).
Each bundle has a runnable Harbor `task/`, the 10× Opus-4.7 eval as a GitHub-rendered
`report.md` (+ plots and reference-vs-candidate galleries), `scores.json/csv`, and a
per-task README. See [`tasks/README.md`](tasks/README.md) for the coverage table.

> **These 11 are Part 1 (static) only.** Part 2 (animations) was attempted but is a
> rushed prototype, so it is deliberately kept out of the final tasks — see below.

---

## Part 2 — Animations (a time-boxed attempt)

Part 2 of the brief — replicate *animations* — was attempted in the time left after
Part 1. It is **a working prototype, not a finished part**: the research is incomplete
and the code is rougher. It reuses the same recipe shape — **generate → gate → curate →
grade with Claude Code + Opus 4.7 → report** — with the fundamental **static → animated**
changes:

- a deterministic **filmstrip** render — frames seeked along the CSS timeline, so they
  are byte-reproducible across machines (the agent gets timed frames, *not* video);
- a new reward, `mean(static_design, motion, animation_judge)`, where **`motion`** is a
  deterministic spatio-temporal signature and `static_design` reuses Part 1's grader on
  the at-rest frame;
- a **two-pass** LLM generator and a deliberately **lean gate** (**95% yield, 19/20**, vs
  Part 1's stricter multi-check gate).

A perturbation ladder proves *higher reward = better animation*, the same shape as Part 1.
Because the research is unfinished, **these tasks are kept out of the final
[`tasks/`](tasks/) set**; the preliminary animation tasks + reports live under
[`task2/tasks/`](task2/tasks/) — 10 tasks (000–009), each with the 10× Opus-4.7 eval as
a report with **animated-GIF** reference-vs-candidate galleries. The known headline
limitation (a fixed 6-frame filmstrip, strict about small timing offsets) and the early
findings (Claude builds **shorter** pages and **slower** entrances) are analysed honestly
in the Part-2 docs.

→ **Everything Part 2: [`task2/README.md`](task2/README.md)** — design, the `motion`
metric in detail, the scaling pipeline, the throughput trade, and limitations.

---

## Quickstart

**Just want to look?** Browse [`tasks/`](tasks/) on GitHub — every task's screenshots
and `report.md` render in place, no clone needed.

**To run it:**

```bash
# 1. Environment (uv, Python >=3.12)
uv venv && source .venv/bin/activate
uv pip install -e ".[grade,modal]"
playwright install chromium          # the grader renders HTML headless, offline
# OCR (the `content` term) needs the tesseract binary locally:
#   macOS: brew install tesseract   |   Debian/Ubuntu: apt-get install tesseract-ocr

# 2. Credentials — env vars, no committed secrets (see note below)
export ANTHROPIC_API_KEY=sk-ant-...
```

The editable install above puts `webdesign_rl` on your path, so the scripts run
directly — no `PYTHONPATH` needed:

```bash
# Reproduce the grader-validation proof above (perturbation study -> curves)
python scripts/validate_grader.py

# Evaluate a task: Claude Code + Opus 4.7 x10 on Modal, graded + reported
python scripts/evaluate.py --task tasks/000_saas-landing_swiss-editorial_low/task --name my-eval --yes
python scripts/report.py jobs/my-eval --format markdown

# Generate a fresh batch on Modal, then pull it down
python scripts/generate.py --count 4 --concurrency 4 --volume my-batch
python scripts/pull_artifacts.py --volume my-batch
```

The grader itself is `python -m webdesign_rl.grade` (what each task's `tests/test.sh`
runs inside the Harbor verifier). Operational detail in the runbooks:
[grading](documentation/runbooks/harbor_grading.md) ·
[batch generation on Modal](documentation/runbooks/modal_batch.md).

> **Credentials (clone-and-go):** `export ANTHROPIC_API_KEY` covers grading + eval.
> Cloud *generation* additionally needs Modal auth (`modal token new` or
> `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET`) plus a one-time `modal secret create
> anthropic-api-key ANTHROPIC_API_KEY=…` — the cloud worker reads the key from a Modal
> Secret, not your shell. `pull` needs only the Modal token.

---

## How it works

- **Grader** — four equal-weighted terms, `reward = mean`, averaged over pages:
  `structure` (MS-SSIM), `color` (CIEDE2000), `content` (OCR word-F1), `design_judge`
  (VLM rubric, Sonnet 4.6 — *Sonnet judges Opus to avoid self-preference bias*).
  Rendered via a **deterministic offline render with bundled fonts** so the same HTML
  always yields the same pixels (a real font-substitution bug forced this — see the
  trail). → [`grader_design.md`](documentation/design/grader_design.md)
- **Generator** — a **3-stage concept→code pipeline** (design system → layout → code),
  **stratified across a taxonomy** (10 archetypes × 10 aesthetics × 3 complexity
  levels), with a deterministic **quality gate** (substance floor, static-only,
  font-palette compliance). Direct Anthropic API calls (not Claude Code) for per-stage
  temperature + parallelism control. → [`generator_design.md`](documentation/design/generator_design.md)
- **Eval** — Claude Code + Opus 4.7 run **10×** via Harbor on Modal, graded, harvested
  into a per-task visual report. → [`eval_pipeline.md`](documentation/design/eval_pipeline.md)

---

## The research and the reasoning trail

Research taste is visible decisions plus the evidence that settled them — including the
dead-ends. So beyond the polished design docs:

- **Grader research** — [`grader_design.md` → "How the field grades design fidelity"](documentation/design/grader_design.md#research-how-the-field-grades-design-fidelity-deep-research-2026-05-30):
  a deep review of how the Design2Code-family benchmarks score replication (the
  single-most-important finding, a per-benchmark breakdown, adversarially verified) and
  how it shaped the four-term blend.
- **Generator research** — [`generator_research.md`](documentation/design/research/generator_research.md):
  the field study behind the 3-stage pipeline (22 sources, with refuted claims listed
  honestly).
- **[`documentation/thinking_trail.md`](documentation/thinking_trail.md)** — the raw,
  timestamped development log: real-time thinking, the bugs hit (the font/SSIM gotcha),
  and the commands run at each step.
- **[`documentation/prds/`](documentation/prds/)** — the development arc as PRDs +
  issues, in build order (grader-mvp, site-generator, eval-pipeline).

---

## Repository layout

```
src/webdesign_rl/   the pipeline: generate/ · grade/ · render/ · emit/ · eval/
scripts/            thin CLIs: generate · pull_artifacts · curate · evaluate(_all) · report(_all) · validate_grader
tasks/              the 11 final tasks (runnable task/ + GitHub-rendered report.md) — Part 1
reports/grader-validation/   the "higher reward = better" proof (curves + scores)
documentation/      index.md (start here) · design/ · runbooks/ · research/ · thinking_trail.md · prds/
templates/          Harbor task scaffolding (task.toml, instruction, test.sh, Dockerfile)
tests/              behavioral test suite (337 passing)
task2/              Part 2 (animations) — a time-boxed prototype: filmstrip grader + scaling pipeline (see task2/README.md)
```

---

## How the 11 final tasks were produced

The exact end-to-end run behind this submission — over-generate, gate, curate, evaluate,
report, then a manual final selection. Generation ran on the Modal app `webdesign-rl-batch`,
persisting artifacts to the Modal volume
[`webdesign-rl-artifacts`](https://modal.com/storage/proximal/main/volumes/webdesign-rl-artifacts):

```bash
# 1. Over-generate a batch on Modal (the quality gate drops the failures)
python scripts/generate.py --count 50 --concurrency 10 --volume webdesign-rl-artifacts

# 2. Pull the batch down locally
python scripts/pull_artifacts.py --volume webdesign-rl-artifacts --out out/batch-50

# 3. Curate: keep the gated survivors (each has a task/), dedup
python scripts/curate.py --batch out/batch-50 --out out/passed-batch-50

# 4. Evaluate every survivor: Claude Code + Opus 4.7 x10, a couple in parallel
python scripts/evaluate_all.py --batch out/passed-batch-50 --parallel 2 --yes

# 5. Build a GitHub-renderable report for every job
python scripts/report_all.py jobs/ --format markdown

# 6. Eyeball trajectories interactively (the per-task report.md is the real results view)
harbor view jobs/

# 7. MANUAL: select the final 11 for distribution + complexity + visual quality,
#    then copy each into tasks/ (035 sourced from the clean opus47-035 run)
```
