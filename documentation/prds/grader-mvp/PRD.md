# PRD: Web Design Replication Grader (Part 1 MVP)

Status: ready-for-agent

> Scope: the **grader** only — the component that scores how faithfully a coding agent
> replicated a multi-page web design from screenshots. Site generation, animations
> (Part 2), and additional frameworks (Part 3) are out of scope here. Grounded in
> `docs/design/grader_design.md` (decisions + grill session, 2026-05-30).

## Problem Statement

We are building Harbor RL environments that test a coding agent's ability to replicate a
multi-page web design from screenshots. The reward signal is the product: the model learns
whatever the grader rewards, so a noisy, discrete, or gameable grader actively makes the
trained model worse. We need a grader that (a) scores design replication on a **continuous
spectrum**, (b) is **robust and low-variance** so identical work scores identically,
(c) **cannot be gamed** by degenerate outputs, and (d) is **provably monotonic** — higher
reward must correspond to a better replication, with evidence, not assertion. None of this
exists yet; the repo is a scaffold.

## Solution

A grader that compares the agent's **rendered** output against the **reference
screenshots** (the only ground truth available at grade time — no source-code access) and
emits a continuous, multi-dimensional `reward.json`.

For each page, the grader renders the agent's HTML/CSS deterministically and computes four
equally-weighted [0,1] terms, each catching a different failure mode:

- **`structure`** — grayscale SSIM (layout/structural arrangement)
- **`color`** — k-means palette + frequency-weighted CIEDE2000 (perceptual color fidelity)
- **`content`** — Tesseract OCR + word-multiset F1 (text correctness; the anti-gaming anchor)
- **`design_judge`** — a vision-LLM rubric averaged to one score (holistic, human-aligned)

Per-page scores are averaged across the site into a scalar `reward`. A **validation
harness** proves the grader sound by showing reward decreases monotonically as a reference
is progressively perturbed, that degenerate outputs score at the floor, and that the
ground-truth oracle scores ≈ 1.0. The grader runs standalone for development and is packaged
into a Harbor **separate verifier environment** for trials.

## User Stories

1. As an RL engineer, I want the grader to output a continuous [0,1] reward, so the model receives a smooth gradient instead of a discrete pass/fail.
2. As an RL engineer, I want the reward decomposed into named sub-scores (`structure`, `color`, `content`, `design_judge`), so I can diagnose what the model fails at.
3. As an RL engineer, I want three of the four terms to be deterministic, so repeated grading of identical output is low-variance and the VLM term contributes at most ~25% of the scalar.
4. As an RL engineer, I want the grader to compare only against the reference screenshots (never the reference source), so I never reward information the agent could not see.
5. As an RL engineer, I want a fixed viewport width stated in the task instruction, so the agent is not penalized for a width it was never told.
6. As an RL engineer, I want screenshot→filename mappings fixed up front (e.g. `home.png`→`home.html`), so grading is deterministic and not a fuzzy file-matching inference problem.
7. As an RL engineer, I want a missing required page to score 0 across all its dimensions, so the model is pushed to produce every page.
8. As an RL engineer, I want rendering to be deterministic (offline, bundled fonts, local assets), so the same code scores the same every run.
9. As an RL engineer, I want the candidate served over a local HTTP server (not file://), so relative asset paths and @font-face load correctly and reproducibly.
10. As an RL engineer, I want full-page screenshots normalized by resizing the candidate to the reference dimensions, so the whole design is graded and height mismatch becomes a fair penalty.
11. As an RL engineer, I want the `structure` term computed on grayscale, so it stays orthogonal to the `color` term and does not double-count color.
12. As an RL engineer, I want the `color` term to use a dominant-palette + CIEDE2000 comparison with a fixed clustering seed, so it is perceptually meaningful, deterministic, and not gameable by matching mean color.
13. As an RL engineer, I want the `content` term to be OCR-based and independent of the VLM, so it remains a real anti-gaming check that catches "right vibe, wrong text."
14. As an RL engineer, I want the `content` term scored as word-multiset F1, so missing text (recall) and hallucinated text (precision) are both penalized and the measure is order-robust.
15. As an RL engineer, I want the VLM judge to return a small rubric (layout/alignment, color/palette, typography, content-completeness) averaged into one `design_judge` score, so it is interpretable and lower-variance than a single holistic number.
16. As an RL engineer, I want the VLM judge to use a different model than the agent under test, at temperature 0, so self-preference bias and nondeterminism are minimized.
17. As an RL engineer, I want the four per-page terms equally weighted (0.25 each) for the MVP, so aggregation is an unbiased baseline that later optimization must beat.
18. As an RL engineer, I want per-page scores averaged into the task scalar, so a site-level reward reflects all pages.
19. As an RL engineer, I want `reward.json` to contain the scalar `reward` plus the four page-averaged dimensions, so Harbor's RL path can read `rewards["reward"]` and I still get interpretable dims.
20. As an RL engineer, I want a `reward-details.json` with the full per-page, per-metric breakdown, so the report and Harbor viewer can show exactly where points were lost.
21. As an RL engineer, I want the grader runnable as a standalone function on two directories, so I can iterate on metrics without spinning up Harbor.
22. As an RL engineer, I want the grader packaged as a Harbor separate verifier environment, so the grading code is hidden from the agent and runs in a clean deterministic image.
23. As an RL engineer, I want the agent's output delivered to the verifier via Harbor artifacts, so a separate verifier env can grade it.
24. As an RL engineer, I want a perturbation harness that degrades a reference in ordered steps (image-space and a few re-rendered source edits), so I can manufacture a known-correct ranking with no human labeling.
25. As an RL engineer, I want each metric validated as monotonic on its own axis (color term responds to color drift, structure to layout shift, etc.), so I trust each term before blending.
26. As an RL engineer, I want the aggregate reward validated as monotonic against perturbation severity (rank correlation), so I can show higher reward = better replication.
27. As an RL engineer, I want degenerate outputs (blank, solid-color, lorem-ipsum) to score at the floor, so I have evidence the reward cannot be trivially gamed.
28. As an RL engineer, I want the ground-truth oracle to score ≈ 1.0, so the top of the scale is calibrated.
29. As an RL engineer, I want a visual report (reward vs perturbation severity, per-metric curves, floor/ceiling anchors), so the grader's soundness is reviewable at a glance.
30. As a coding agent, I want an instruction that lists each screenshot, its required output filename, and the render viewport, so I know exactly what to produce.
31. As the model being trained, I want the reward to track genuine design fidelity across layout, color, text, and holistic look, so optimizing the reward improves real replication.
32. As a maintainer, I want the grader's external behavior covered by tests (identical→1.0, degenerate→~0, monotonic perturbations, missing-page=0), so refactors do not silently break the reward.
33. As a maintainer, I want the VLM judge isolated behind an interface, so the deterministic logic can be tested without live API calls.

## Implementation Decisions

**Module decomposition (deep modules, simple stable interfaces):**

- **Render module** — renders a site directory to per-page full-page screenshots. Interface: takes a site directory, a page map, and a viewport spec; returns one image per page. Serves the directory over a local HTTP server, drives an offline headless browser with a bundled font set, captures full scroll-height at a fixed width (default 1280px). Deterministic by construction.
- **Four metric functions** — each takes a candidate image and a reference image and returns a float in [0,1]:
  - `structure`: grayscale single-scale SSIM (scikit-image).
  - `color`: k-means dominant palette (~6 colors, fixed random seed) on both images, frequency-weighted nearest-neighbor CIEDE2000 in Lab, normalized `max(0, 1 − ΔE/100)`.
  - `content`: Tesseract OCR text from both images, normalized, scored as word-multiset F1.
  - `design_judge`: one call to a vision LLM (Sonnet-class, distinct from the agent model, temperature 0) given both labeled images; returns a small numeric rubric; the module averages the rubric to one [0,1] score. This is the only non-deterministic module and is accessed through a thin client interface that can be stubbed.
- **Aggregation module** — pure function combining per-page, per-dimension scores into the `reward.json` payload. A page score is the mean of its four terms; the task `reward` is the mean across pages; a required page absent from the candidate contributes 0 across its dimensions.
- **Grader orchestrator** — wires render → metrics → aggregate; writes `reward.json` and `reward-details.json`. Standalone interface takes a candidate directory, a reference directory, and a page map.
- **Perturbation module** — produces ordered degradations for validation: image-space (color drift, blur, spatial shift, region occlusion, noise) and a few source-space edits (remove an element, swap a font, shift the CSS palette, delete text) that are re-rendered; plus degenerate generators (blank, solid-color, lorem-ipsum).
- **Validation harness** — runs the grader across the perturbation ladder and degenerate set, computes per-metric and aggregate monotonicity (rank correlation), checks oracle ≈ 1.0 and floors ≈ 0, and emits the visual report.
- **Emit / task packaging** — assembles a Harbor task from a reference site: instruction (screenshot→filename table + viewport), `task.toml` configured for a **separate verifier environment**, a verifier image carrying the renderer + OCR + fonts + grader, and the agent-output→verifier transfer via the `artifacts` field.

**Data contracts:**

- `page_map` maps a logical page to its reference screenshot and the required candidate filename, e.g. conceptually `{ "home": { "screenshot": "home.png", "expected_file": "home.html" } }`.
- `reward.json` is a flat object: `reward` plus the four page-averaged dimension keys (`structure`, `color`, `content`, `design_judge`), all floats. `reward-details.json` carries the per-page, per-metric breakdown.

**Key behavioral decisions (from the grill):**

- Reference = the screenshots shown to the agent; no source-code access at grade time.
- Capture full-page at fixed width; resize candidate to reference dimensions before pixel metrics.
- Rendering is offline with a local font bundle; identical code must score identically.
- Equal weights (0.25 each) for the MVP; weight tuning is a later optimization, not part of this PRD.
- Reward stays majority-deterministic (3 of 4 terms) so VLM variance cannot dominate.

## Testing Decisions

**What makes a good test here:** assert the grader's **external behavior** — the score a
given input pair produces — not internal implementation (no asserting on intermediate
arrays, library calls, or private helpers). Tests should be deterministic, which is why they
target the deterministic modules and stub the VLM.

**Modules to test (deterministic only, per developer decision):**

- `structure` (SSIM): identical images → 1.0; a clearly different image → meaningfully lower; monotonic decrease under increasing blur/shift.
- `color` (CIEDE2000 palette): identical palette → ≈1.0; a hue-shifted variant scores lower; monotonic decrease as palette ΔE grows; deterministic across runs (fixed seed).
- `content` (OCR F1): identical text → 1.0; missing words lower recall; injected words lower precision; empty candidate → ~0.
- `aggregation`: page score = mean of four terms; task reward = mean across pages; a missing required page contributes 0 and drags the mean; output payload has the expected keys.
- `perturbation`: each generated perturbation level is ordered by severity such that the metric it targets responds monotonically; degenerate generators produce blank/solid/lorem outputs that score at the floor.
- `render` determinism: rendering the same fixed site twice yields byte-stable (or hash-stable) screenshots; output dimensions match the requested viewport width.

**Explicitly minimal for `design_judge`:** test only that the module correctly parses a
**stubbed** rubric response into an averaged [0,1] score and handles malformed/edge responses;
do **not** assert on live model outputs. No live API calls in the test suite.

**Prior art:** the repo already depends on `pytest` + `pytest-asyncio` (in `pyproject.toml`);
tests follow standard pytest structure. Image fixtures are small hand-made reference crops
checked into the test data.

## Out of Scope

- **Site generation** (the taxonomy + LLM generation + quality gate) — separate PRD.
- **Part 2 (animations)** and **Part 3 (React/Tailwind/Solid frameworks)** — only the
  render/metric *seams* are respected (see grader_design.md), nothing is built for them here.
- **`perceptual` term (LPIPS/DISTS)** — explicitly dropped from the MVP (torch dependency).
- **Block-level (Design2Code-style) matching** and **multi-viewport/responsive grading** —
  deferred enhancements.
- **Weight optimization** — equal weights for now; grid-search tuning is future work that
  *uses* the validation harness this PRD delivers.
- **Heavy VLM-judge variance characterization** — a single temp-0 sample for the MVP;
  multi-sample variance measurement is part of the later validation study, not this build.

## Further Notes

- The validation harness is itself a graded deliverable (the "why higher reward = better
  replication" evidence), so it is in scope here, not deferred.
- The grader-first build order is deliberate: the grader can be fully validated with one
  hand-made reference site and programmatic perturbations, with no generator — see
  `docs/design/grader_design.md` for the asymmetry argument.
- Spike order: build and validate the four metrics on one rich hand-made page, then extend
  to a 5-page hand-made site for multi-page aggregation and the report.
- The font bundle contents, generated-site asset strategy, and per-block OCR upgrade are
  open but non-blocking and tracked in the design doc.
