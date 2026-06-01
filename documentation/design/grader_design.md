# Grader Design

> Status: **built.** The 4-term grader (structure / color / content / design_judge,
> equal-weight mean) is implemented and validated — see the monotonicity study in
> `reports/grader-validation/`. This doc records the decision rationale up top; the
> "open questions" section below is preserved as the original research/grill trail
> (since resolved into the design above).

---

## Why we build the grader before the generator

The reward function is the **product**. The model trained on these tasks learns *our
grading logic* — if the grading is noisy or wrong, we are not training a better model, we
are injecting noise and making it worse. So the grader is not plumbing around the "real"
work of generating sites; it _is_ the real work. We build the product first.

The decisive argument is an **asymmetry in how the two components can be validated:**

> A **grader can be validated with no generator.**
> A **generator cannot be validated with no grader.**

- To validate the grader, we need **one** reference site (hand-authored is fine) and a set
  of **programmatic perturbations** of it — drift the palette, shift the layout, drop a
  section, swap the fonts, degrade spacing. Each perturbation comes with a **known
  ordering**: a 10% color drift is objectively closer to the reference than a 50% drift.
  That gives us labelled `(input, expected-rank)` pairs **for free**, with no LLM
  generation and no compute fan-out. We then check that the grader's rewards **respect
  that ordering** (the monotonicity study). This is a cheap, self-contained, day-one test.

- The reverse is impossible. The moment we generate sites, the only way to know whether a
  generated site is _good_ — varied enough, gradeable, not degenerate — is to **grade it**.
  The generator's acceptance test _is_ the grader.

So the dependency arrow points one way: the grader unblocks evaluation of the generator,
not vice versa. Building it first de-risks the highest-uncertainty piece of the project
for the cost of one hand-made HTML page, instead of after burning generation + eval
compute.

Supporting reasons:

- **Highest uncertainty lives here.** LLMs reliably produce decent multi-page sites;
  generation is comparatively known. Whether _our metrics actually track design quality_
  is the genuinely open question. Front-load the risk.
- **It produces a reusable gate.** The Phase-1 validation harness (oracle ≈ 1.0, blank
  ≈ 0.0, monotonic perturbation curve) becomes the **automated acceptance test** every
  generated task must pass later.

**Honest caveat:** grader-first means hand-authoring 1–2 reference sites to develop
against, which feels like throwaway work. It isn't — those sites become the grader's
regression fixtures and the perturbation study in the final report.

> Note: "good tasks" (diverse, complex, human-like sites) is a **co-equal product goal**,
> not a lesser one — the brief judges both. Grader-first is a statement about _build
> order_, not _importance_. The diversity strategy lives in
> [`generator_design.md`](./generator_design.md).

---

## What the grader takes as input

Logically the grader is a pure function:

```
grade(candidate, reference, page_map) -> { "<dim>": float in [0,1], ..., "reward": float }
```

- **candidate** — the agent's output: a directory of HTML/CSS files. The grader **renders
  these itself** (headless browser, fixed viewport) into screenshots. We grade the
  _rendered result_, never the source text — two different DOMs can produce the same look,
  and the brief only cares about design.
- **reference** — the ground-truth target. Because we generated the site, this is the
  committed reference screenshots (or the reference source re-rendered at grade time, same
  viewport — apples to apples).
- **page_map** — which candidate file maps to which reference page (e.g. `index.html ↔
  home`), so the right pairs are compared across all ≥5 pages.

In the packaged Harbor task this same logic lives in `tests/test.sh`: render the agent's
`/app` files → compare to the reference → write `/logs/verifier/reward.json`.

---

## Research: how the field grades design fidelity (deep-research, 2026-05-30)

A fan-out deep-research pass (22 primary sources, 25 claims adversarially verified, 1
refuted). **Evidence labelling matters here:** the *benchmark metric decompositions* below
are verified from papers + official code (verbatim-grounded). The *per-family intrinsic
scorecard* further down is **standard-knowledge engineering judgment**, not verified by this
research pass — the search did not surface head-to-head metric-property studies, so treat
that table as a hypothesis to test in our own monotonicity study, not as cited fact.

### The single most important finding

**Every serious screenshot-to-code benchmark grades with a _multi-dimensional
decomposition_, never a single fidelity number.** This directly validates the multi-metric
`reward.json` direction. The dimensions recur across papers: **layout/position, color,
text/content, structure, and a perceptual/semantic anchor**.

### How each benchmark actually grades (verified)

| Benchmark | How it grades fidelity | Notes for us |
| --- | --- | --- |
| **Design2Code** (Stanford, 2024) | **5 components, equal-weighted 0.2 each** in the public code: (1) **Block-Match** = matched area / total area (penalizes missing + hallucinated blocks); (2) **Text** = char-level Sørensen-Dice / `SequenceMatcher` ratio; (3) **Position** = `1 − normalized Chebyshev` center offset; (4) **Color** = **CIEDE2000** Lab ΔE, `max(0, 1−ΔE/100)`; (5) **CLIP-ViT-B/32** cosine, **with text inpainted out** (Telea) so text doesn't contaminate the visual score. Text blocks are detected on the **image** and optimally paired via Hungarian/Jonker-Volgenant assignment (match threshold ≥0.5). | **The canonical decomposition; adapt directly.** Crucially, block detection + matching run on the **screenshots**, not source — compatible with our "screenshots-only" constraint. The paper keeps dims **separate as diagnostics**; only the code applies the 0.2-each blend. |
| **Sketch2Code** (2024) | Reuses the Design2Code 5-component average **+** an **area-weighted per-type IoU** layout metric over 7 component types (text, image, video, nav, form/table, button, divider). | IoU layout is appealing but its **human-correlation claim was REFUTED (0–3)** in our verification — do **not** treat per-type IoU as a human-validated proxy. Also relies on element detection (see weakness below). |
| **Web2Code / WCGB** (NeurIPS 2024) | Re-renders predicted HTML (Selenium) → screenshot → **VLM-as-judge (GPT-4V)** scores **10 criteria in 4 dims, 0–10**: Visual Structure & Alignment, Color & Aesthetic, Textual & Content, UI & Interactivity. | Motivation = "same page, many codes" → grade the **image**, not the code string. Smooth 0–10 = good continuity; cost + variance from the VLM. |
| **Interaction2Code** (ASE 2025) | **CLIP** (visual) + **SSIM** (structure) + **OCR→BLEU** (text) + **widget matching**. | **Concrete warning:** widget-detection similarity "**consistently poor**" on web UIs — mobile-style detectors don't scale to web complexity. Argues against element-detection-heavy structural terms. |
| **DesignBench** (2025) | **CLIP** (semantic) + **SSIM** (layout/spatial) + **GPT-4o judge** for design edit/repair. | VLM judge hit **95.5% / 91.9%** agreement with humans (κ≈0.86) — evidence VLM-judge *can* be human-aligned on rubric judgments (authors' own validation, so weight accordingly). |
| **UI2Code^N** (Nov 2025) — *the RL-specific one* | Trains with a **VLM-as-judge (GLM-4.5V) as a continuous reward** normalized to [0,1]; **explicitly rejects CLIP cosine as a reward** — "brittle, oversensitive to positional shifts and background colors yet blind to fine details." Ablation: **RL-CLIP reward = 62.0 vs RL-VLM-judge = 74.6** on Design2Code (CLIP reward even degraded below the SFT baseline). | **Most decision-relevant for us.** Do **not** make CLIP the reward. *Caveat:* single non-replicated ablation from authors (Zhipu) who also build the winning judge GLM-4.5V — possible self-interest; verify in our own monotonicity study. |

### Per-family scorecard (engineering judgment — NOT from the verified claims; test it)

Scores are qualitative (✓✓ good → ✗ bad) **for our use** (continuous reward, screenshots-only,
multi-page static HTML/CSS). Verified caveats are flagged inline.

| Method family | Continuity | Robustness to trivial shifts | Gameability (low = hard to game) | Determinism | Cost |
| --- | --- | --- | --- | --- | --- |
| **MSE / PSNR** | ✓✓ smooth | ✗ 1px shift = catastrophic | ✗ (avg-color/blur tricks) | ✓✓ exact | ✓✓ trivial |
| **SSIM / MS-SSIM** | ✓✓ smooth | ✗→~ shift-sensitive (MS better across scales) | ~ | ✓✓ exact | ✓✓ low |
| **LPIPS / DISTS / DreamSim** | ✓✓ smooth | ✓ learned tolerance (DISTS best to mild geometric/texture; DreamSim human-tuned) | ~ | ✓ deterministic (fixed weights) | ✓ one fwd pass |
| **CLIP cosine** | ~ | ✗ *verified brittle* — oversensitive to position/bg, blind to detail | **✗ verified gameable** (high score, wrong page) | ✓ deterministic | ~ moderate |
| **DINOv2 cosine** | ✓ | ✓ better spatial sensitivity than CLIP (not verified here) | ~ | ✓ deterministic | ~ moderate |
| **Block/element IoU matching** | ~ (matching threshold adds cliffs) | ~ depends on detector | ~ | ~ detector-noise | ~ moderate; **widget detection verified weak on web** |
| **DOM / tree-edit distance** | ✗ discrete-ish | n/a (needs DOM) | ~ | ✓ | ✓ low — but **penalizes same-look/different-DOM → unfair for us**; reject |
| **CIEDE2000 color** | ✓✓ smooth, perceptually uniform | ✓✓ position-independent | ~ (color only, ignores layout) | ✓✓ exact | ✓✓ trivial |
| **Text / OCR match** | ✓ (string-sim continuous) | ✓✓ layout-independent | **✓✓ hard to fake correct text** | ✓ (OCR mostly deterministic) | ✓ low |
| **VLM-as-judge** | ✓✓ smooth, human-aligned | ✓✓ semantic | ✓ low-ish | **✗ noisy** (temp/prompt/test-retest variance) | **✗ API cost per grade** |

### What this means for our grader

1. **Multi-dimensional reward is the consensus — build the blend, not a single metric.**
2. **CLIP must not be the sole/primary reward** (verified, RL-specific). It can stay as a
   weak semantic anchor at most; prefer **LPIPS/DISTS/DreamSim or DINOv2** for the
   perceptual term, or a **VLM-judge** for global fidelity.
3. **Block detection runs on screenshots, not source** — this is how Design2Code already
   works, so a Design2Code-style decomposition is **fully compatible with the
   screenshots-only stance** in `human_notes/scratchpad.md`. The leak concern doesn't bite,
   because we detect/compare on rendered images on both sides.
4. **Don't lean on element/widget detection for structure** (verified weak on web). Prefer
   **SSIM/MS-SSIM + matched-text-block position** for layout, which need only text-block
   detection (more reliable) rather than full widget taxonomies.
5. **Text/OCR content match is our best anti-gaming term** — cheap, deterministic, and very
   hard to score high while wrong.
6. **VLM-judge buys continuity + human alignment but is the variance/cost sink** — use it as
   *a term*, not the whole reward; measure its test-retest variance before trusting it.

### Recommended blend (provisional — to confirm in the grill + monotonicity study)

A weighted, screenshots-only, per-page score, mapped to interpretable `reward.json` dims:

| `reward.json` dim | Metric | Role |
| --- | --- | --- |
| `layout` | matched-text-block **position** (1−Chebyshev) + **MS-SSIM** | spatial arrangement |
| `color` | **CIEDE2000** on matched regions / palette | perceptually-uniform color fidelity |
| `content` | **OCR text** matched per block (Sørensen-Dice / BLEU) | anti-gaming; missing/wrong/hallucinated text |
| `structure` | **block-match** area (matched / total incl. hallucinated) | completeness of elements |
| `perceptual` | **LPIPS or DISTS** (not raw CLIP) | global look anchor |
| `design_judge` *(optional)* | **VLM rubric** (WCGB-style 0–10 dims) | human-aligned global fidelity / aesthetics |
| `reward` | weighted aggregate | the scalar the RL framework consumes |

Starting weights: Design2Code's uniform split is a defensible default; keep `design_judge`
a **minority term** to cap variance/cost. Final weights are an output of the **monotonicity
study** (pick weights that maximize monotonic response to controlled perturbations).

### Still-open questions the research did *not* settle

- Head-to-head intrinsic properties of MSE/SSIM/LPIPS/CLIP/DINOv2 (we'll measure these
  ourselves via perturbations — that's exactly what the validation plan does).
- VLM-judge **variance** as a continuous reward (test-retest / temperature / prompt) — must
  measure before trusting.
- **Multi-page aggregation** weighting (mean vs worst-case vs nav-consistency) — unsettled.
- **OCR-free vs OCR-based** text-block detection: which is less gameable for static HTML.

Full source list + verification votes: see the deep-research run (Design2Code
[paper](https://arxiv.org/pdf/2403.03163) / [code](https://github.com/NoviScl/Design2Code),
Sketch2Code [2410.16232](https://arxiv.org/pdf/2410.16232), Web2Code
[2406.20098](https://arxiv.org/html/2406.20098v2), Interaction2Code
[2411.03292](https://arxiv.org/html/2411.03292v3), DesignBench
[2506.06251](https://arxiv.org/html/2506.06251v3), UI2Code^N
[2511.08195](https://arxiv.org/html/2511.08195v1)).

## Open questions (to resolve via research + grill)

These were the open questions at design time; the trail of how they resolved is in
[`../thinking_trail.md`](../thinking_trail.md).

- **Which signals, and how weighted?** Candidate families:
  - Perceptual image-embedding similarity (DINO/CLIP) — robust, continuous, captures look.
  - Pixel / SSIM diff — precise but brittle to small shifts.
  - Structural layout match — major-region bounding-box IoU.
  - Color-palette and typography distance — cheap, objective, interpretable.
  - LLM-as-judge over screenshot pairs — human-like, multi-dimensional, but noisier/gameable.
- **Single blended reward vs. multiple named sub-rewards** in `reward.json`?
- **How to combine across ≥5 pages** (mean? worst-case? nav-consistency term?).
- **Gameability** — what degenerate output could score high that shouldn't? How do we
  defend against it?
- **Continuity guarantees** — does each candidate metric vary smoothly with design quality,
  or have cliffs that would teach the model noise?
- **Cost / determinism** — LLM-judge variance and price vs. deterministic metrics.

## Forward compatibility: Parts 2 & 3 (design the seam, don't build it)

We design the grader so Parts 2 and 3 slot in **without a rewrite**, but we **build only
Part 1** behind these seams. This is interface shape, not extra code — the brief is
emphatic that a high-taste Part 1 beats a rushed all-parts, so anything beyond the cheap
seams is explicitly deferred (no plugin framework on day one).

**Why this works:** because we grade **rendered output, not source**, the comparison core
sees only pixels — it does not care whether they came from HTML, React+CSS, React+Tailwind,
or Solid+Tailwind. Part 3 becomes "add a render adapter," not "redesign the grader." And
since the Part 3 deliverable is a *cross-framework benchmark*, scores are only comparable
if the **same grader** scores every framework — a framework-agnostic core is required, not
just convenient.

Part 2 (animations) is the one that genuinely **adds a dimension** rather than swapping an
adapter: static fidelity still applies (keyframes must look right) *plus* a motion-fidelity
score. It slots in if the reference is a **frame sequence** from the start.

### Load-bearing seams — honor now (≈ free)

| Seam | Why it prevents rework |
| --- | --- |
| Comparison core consumes **rendered frames, never source** | Already decided; makes Part 3 a render-adapter swap |
| Rendering is a **pluggable adapter** `render(candidate, viewport, page_map) -> frames` | Part 3 = add React/Solid adapters; core unchanged |
| Reference = **per-page list of frames** (Part 1 = length 1) | Part 2 extends to sequences with no reshaping |
| `page_map` abstracts **target identity** (filename *or* route) | React/Solid use routes, not `.html` files |

### Defer — do NOT build now

- Temporal motion metrics (optical flow, easing-curve extraction) — Part 2.
- React/Solid build toolchains in the verifier container — Part 3.
- Multi-viewport / responsive grading — not required by the brief.

### The one Part-2 assumption that constrains the grader's shape

**Fixed capture protocol** — the temporal analog of the fixed-viewport decision. Because we
*generate* the animations from scratch, we control both the animation vocabulary and the
capture. Both the reference video and the candidate's are recorded by driving the **same
scripted interaction at the same timing** (load → wait → scroll to Y → hover element X), so
frames are **temporally aligned** and the comparison is well-posed. Without it we'd compare
two unaligned videos — pure noise. (A VLM judge extends naturally to video, so the first
version of motion grading can reuse the judge dimension; heavyweight programmatic motion
metrics are deferred.) Everything else about Part 2 — *which* animations exist — is a
generation concern, not a grader concern.

## Validation plan (the evidence the grader is good)

- **Monotonicity study** — reward decreases monotonically as a reference is progressively
  perturbed. _This curve is the core evidence for "higher reward = better replication."_
- **Oracle ceiling** — the ground-truth site scores ≈ 1.0.
- **Floor** — blank / random HTML scores ≈ 0.0.
- **Discrimination** — clearly-better replications outscore clearly-worse ones on held
  examples.

## Scope decision: the 3-day MVP blend (what we build now)

Given the timeline (3 days, all parts), we subselect the metrics with the highest
**utility-per-overhead**. Guiding principle: **preserve the diversity-of-failure-modes
anti-gaming property with the fewest moving parts, and keep the _majority of terms
deterministic_ so VLM-judge variance can't dominate the reward.**

> Correction to a common assumption: **LPIPS/DISTS/DreamSim do _not_ require training a
> CNN** — they ship pretrained and are a one-line install. Their real cost is the **torch
> dependency + model download**, not training. So the scope line is "no torch-heavy or
> bespoke-detection pipelines in the MVP," not "no learned metrics."

### Core — build now (1 holistic + 3 deterministic, each catches a different failure)

| Term | `reward.json` dim | Why high-utility now | Overhead |
| --- | --- | --- | --- |
| **VLM-judge** (multi-dim rubric, one call) | `design_judge` (+ layout/color/content sub-dims) | Strongest single signal in the research (UI2Code^N, DesignBench); human-aligned + continuous; **one Claude vision call returns several sub-scores**. API key already available. | **Low** (API only) |
| **SSIM** (grayscale) | `structure` | Deterministic structural/layout anchor; catches layout errors a generous judge may miss. Grayscale single-scale (true MS-SSIM needs torch). | **Low** (`scikit-image`, no torch) |
| **CIEDE2000 palette distance** | `color` | Deterministic, perceptually-uniform color fidelity; **palette-level → no block-matching needed**. | **Low** (small Lab conversion) |
| **OCR text match** | `content` | Key **anti-gaming** term; **independent of the VLM** so it can't be co-gamed; catches "right vibe, wrong substance." | **Medium** (Tesseract in the verifier image) |

The three deterministic terms also **cross-check the VLM**: if the judge says 0.9 while
SSIM/color/OCR say 0.4, the judge has drifted. So even the MVP is defended against the
variance weakness the research flagged about VLM rewards.

### Excluded from the MVP (avoid over-engineering)

- **`perceptual` (LPIPS / DISTS)** — **dropped from the MVP.** Pretrained (no training), but
  it adds a torch dependency and SSIM + the VLM judge already cover structure and holistic
  look. Not worth the overhead at this stage; revisit only if the validation study shows a
  real gap the other four terms miss.

### Deferred — correct call for a 3-day build

- **Design2Code block-match + position** — high value, but text-block detection + Hungarian
  matching is the most integration overhead; MS-SSIM + the VLM layout dim approximate it for
  now. Add later if time.
- **CLIP / DINOv2 embeddings** — CLIP is verified gameable; both add torch. Skip.
- **Pixel MSE/PSNR** (low value, brittle) and **DOM/tree-edit** (unfair to same-look/
  different-DOM; needs DOM). Skip.
- **Training any CNN** — out of scope.

### MVP reward — equal weights for now

```
reward = mean(design_judge, structure, color, content)   # 0.25 each
```

**Decision: start with equal weights (0.25 each) across the four core terms.** Rationale:
with no validation data yet, equal weighting is the honest, unbiased default and keeps the
MVP simple — we are not over-engineering the aggregation before we can measure it. The
weights are a **later optimization**: once the perturbation/monotonicity study exists, we
fit them by grid-search under the Validation-plan constraints (monotonic on perturbations,
degenerate outputs at the floor, oracle ≈ 1.0). Equal-weight is the baseline that
optimization must beat.

Note: equal weighting still keeps the reward **majority-deterministic** (3 of 4 terms), so
VLM-judge variance contributes only ~0.25 of the scalar — the anti-variance property holds
without any tuning.

## Implementation decisions (grilled, 2026-05-30)

Resolved via a grill session, in dependency order. These are the concrete choices needed to
write the grader; each lists the decision and the one-line reason.

| # | Decision | Choice | Why |
| --- | --- | --- | --- |
| 1 | **Capture & normalize** | Full-page screenshot at fixed width; **resize candidate → reference dims** before pixel metrics | Grades the whole design; height mismatch becomes a fair vertical-squash penalty; VLM sees both natively |
| 2 | **Render determinism** | **Local font bundle, offline render** (internet disabled); local/inline assets | Same code must score the same every run; we control generation so we control the font palette |
| 3 | **VLM judge output** | Decomposed rubric (layout/alignment, color/palette, typography, content-completeness) 0–10 with anchors → **mean = `design_judge`**; sub-scores logged to `reward-details.json` | Interpretable + lower variance than one holistic number; stays a single MVP term |
| 4 | **Judge model** | **Sonnet 4.6** (deliberately ≠ the Opus 4.7 agent under test), temperature 0, **k=1** | Avoids self-preference bias; cheap; measure variance later, escalate to k=3 only if needed |
| 5 | **`structure` term** | **Grayscale single-scale SSIM** via scikit-image (no torch); grayscale keeps it orthogonal to `color` | True MS-SSIM needs torch (excluded); grayscale avoids double-counting color |
| 6 | **`color` term** | **K-means dominant palette** (~6 colors, fixed `random_state`) + frequency-weighted **CIEDE2000**, normalized `max(0,1−ΔE/100)` | Interpretable "palette match"; deterministic with fixed seed; not gameable by mean-color |
| 7 | **`content` term** | **Tesseract** whole-page OCR → **word-multiset F1** (recall=missing, precision=hallucinated) | Deterministic, free, and **independent of the VLM** → real anti-gaming check; order-robust |
| 8 | **Aggregation** | **Mean across pages** (each page = mean of its 4 terms); missing required page = 0 across its dims; `reward.json = {reward, design_judge, structure, color, content}`; per-page breakdown → `reward-details.json` | Simplest defensible default; missing pages drag the mean naturally; RL reads `rewards["reward"]` |
| 9 | **Validation harness** | **Hybrid perturbations** — image-space backbone (color drift, blur, spatial shift, occlusion, noise) + a few re-rendered source degradations (remove element, swap font, shift palette, delete text) + degenerate floors (blank, solid-color, lorem-ipsum); checked per-metric **and** on the aggregate | Image-space proves per-metric monotonicity cheaply; source-space proves realism; floors prove anti-gaming |
| 10 | **Harbor verifier env** | **Separate** verifier environment (Playwright + Tesseract + fonts + grader code); agent output reaches it via Harbor **artifacts** | Hides grading code from the agent (can't game it); clean, deterministic render image |

### Assumed defaults (small; flag to change)

- **Viewport width = 1280px** desktop, full scroll height. Mobile/responsive deferred.
- **Spike order:** build the 4 metrics on **one rich hand-made page**, then a **5-page**
  hand-made site for multi-page aggregation + the report.
- **Render via a local HTTP server** (`http://localhost`), not `file://`, so relative asset
  paths and `@font-face` load correctly and deterministically.
- **Grader contract:** `grade(candidate_dir, reference_dir, page_map, out_dir) → writes
  reward.json + reward-details.json into out_dir` (the `out_dir` arg was added during issue
  01 so writes are deterministic; Harbor packaging passes `/logs/verifier`). `page_map =
  {page: {screenshot, expected_file}}`.

### Open but non-blocking (do not gate the grader build)

- Font-bundle contents (which ~5–10 families) — a generation-side list.
- Image/asset strategy in *generated* sites (CSS-drawable vs placeholder vs generated) — a
  generation concern, not the grader's.
- Per-block OCR/position upgrade (Design2Code-style) — deferred enhancement.
- VLM-judge variance measurement — part of the validation study, not the build.

## Principle: deterministic offline render + bundled fonts (and the issue-07 lesson)

**The principle.** The grader works by comparing *pictures* (rendered screenshots). The
same HTML/CSS can render to *different pixels* depending on the environment, so unless we
pin that environment the reward wobbles for reasons unrelated to the agent's design — i.e.
we'd train the model on noise. So we render every page in **one identical, internet-free
environment with the fonts fixed inside it**, guaranteeing *same code → same picture, every
run, every machine*. Three sources of non-determinism, each removed:

1. **Fonts** → *bundled fonts.* If CSS asks for a font the machine lacks, the browser
   silently substitutes another — different glyph shapes/widths, different line wrapping,
   shifted layout. We fix the font set inside the render environment so a font name always
   maps to the same file everywhere.
2. **Network** → *offline render.* Anything fetched at render time (web fonts, CDN images,
   analytics) can be slow/flaky/time- or location-dependent. We **block all non-local
   requests** during rendering (Playwright route-abort), so a page can only use what ships
   with it. Bonus: this also stops an agent hot-linking the original site's assets.
3. **Browser/machine** → *pinned engine.* One headless Chromium, fixed flags (no GPU, sRGB,
   device-scale-factor 1), fixed **1280px** viewport, animations off.

**Apples-to-apples corollary.** The screenshots *shown to the agent*, the grading
*reference*, and the *candidate's* render must all come from this **same** environment. If
any one differs, even a perfect replica is penalised.

**The issue-07 lesson (why this is load-bearing, not theoretical).** We first committed a
reference PNG rendered on the **macOS host** (which has Arial) but graded the candidate
inside the **Linux container** (which doesn't — it substitutes DejaVu). The *oracle* — a
byte-perfect reproduction of the ground truth — scored `structure` **0.91 instead of 1.0**,
purely because the two renders used different fonts. The metric was correct; the *setup* was
comparing renders from two environments. **Fix:** render the reference **in the same
container** as the candidate (`--reference-site` mode) → oracle = **1.0**, host-independent.

**How fonts are actually bundled today (and where).** Not as `.ttf` files in the repo, but
at the **image** level: the emitted verifier `Dockerfile`
(`src/webdesign_rl/emit/templates.py`) runs `apt-get install fonts-dejavu-core fontconfig`
and bakes Chromium in (`playwright install --with-deps chromium`). Those OS-level fonts are
fixed wherever the self-contained image runs (Docker or Modal). Nothing is passed to
Playwright in Python — `render/browser.py` just launches Chromium, which reads the
*environment's* installed fonts via fontconfig automatically. So we control the fonts by
controlling the **environment** (the image), not by a code argument. The offline route-abort
in `browser.py` ensures no web font can override them.

**Current limitation → generation-phase work.** Today the bundle is just DejaVu, so any CSS
font the container lacks **falls back to DejaVu** — deterministic, but the design's intended
typography may not appear. The fuller version (deferred to generation): curate a small font
palette, install those exact files into the image *and* constrain generated sites to use
only those fonts (referenced via `@font-face`), so typography is both **faithful and
deterministic**. This is the "we control generation, so we control the font palette"
decision (row 2 of the grilled table) — it lands when we build generation, not the grader.