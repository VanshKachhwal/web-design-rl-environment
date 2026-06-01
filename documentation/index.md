# How this was built — documentation hub

This is the narrative spine for the **web-design replication RL environment**: a
scalable pipeline that *generates* web-design tasks from scratch and *grades* a
coding agent's attempt to replicate them from screenshots alone. Everything here is
a curated record of **how the problem was thought through and how each decision was
made** — the brief asks for exactly that, and treats it as the thing that matters
most.

If you read nothing else, read this page top to bottom: it tells the story and
points to the deeper docs as you go.

---

## The brief, and what it rewards most

The [project brief](./project-brief.md) asks for a stable, scalable recipe that
produces design-replication tasks with **continuous** grading (higher reward = better
design), websites **generated from scratch** (no crawling), **≥5 pages** each, and a
**good distribution** of site types. Functionality is out of scope — design only.

But the brief is blunt about priorities:

> *"There is nothing more important than showcasing research taste and good decisions.
> Get Part 1 done really well before moving on."*

So three questions drive everything below, in order:

1. **Is the grading good?** The model learns the grading logic — a bad signal injects
   noise and makes the model worse. This is the centerpiece.
2. **How varied, complex, and human-like** are the generated sites?
3. **What behaviors / learnings** emerge when a real model is evaluated?

The single guiding principle behind these docs: **research taste is visible decisions
plus the evidence that settled them** — including the dead-ends. That's why the raw
[thinking trail](./thinking_trail.md) and the [PRDs + issues](./prds/) ship alongside
the polished design docs.

---

## The through-line: grader-first

We built the **grader before the generator**. You cannot generate sites *toward* a
target you cannot measure, and you cannot trust a reward you have not stress-tested.
So the grader — and the proof that its reward tracks design quality — came first, and
the generator was built to feed it. Full rationale: **[grader_design.md](./design/grader_design.md)**.

---

## How the grader works (and why these choices)

The reward is the **equal-weight mean of four terms**, each chosen to be cheap,
non-gameable, and grounded in prior art (the [research log](./design/research/generator_research.md)
and Design2Code-family benchmarks):

| Term | Signal | Why it's here |
|---|---|---|
| **structure** | MS-SSIM on the rendered page | Catches layout/position drift and hallucinated blocks; cheap |
| **color** | CIEDE2000 palette distance | Perceptually-uniform color difference, not naive RGB |
| **content** | OCR word-multiset F1 | Hard to game; rewards faithful copy, not plausible-looking filler |
| **design_judge** | VLM rubric (Sonnet 4.6) | Holistic "does it look like the target" a pixel metric can't capture |

Three decisions carry most of the taste:

- **Deterministic offline render with bundled fonts.** The reward compares two
  pictures, so the *same* HTML must always produce the *exact same* picture — every
  machine, every run. We render headless Chromium at a fixed 1280px viewport, with the
  network cut and the exact font files bundled into the image. This was not theoretical:
  an early macOS-vs-Linux font substitution silently moved text and tanked SSIM. The
  debugging story and the full "why" are in the [thinking trail](./thinking_trail.md);
  the principle is locked in [grader_design.md](./design/grader_design.md).
- **Sonnet judges Opus.** The agent under test is Opus 4.7; the judge is Sonnet 4.6 —
  a deliberate choice to avoid self-preference bias.
- **Reward validity is *proven*, not asserted.** A perturbation harness degrades a
  golden render along each axis (layout, color, structure) at rising severity; the
  reward must fall **monotonically**. It does. Cross-checked by an **oracle** (grading
  the reference against itself → **0.996**) against a real **Opus run (~0.76)** — a
  large, healthy gap. See the committed validation study in `reports/grader-validation/`
  and the operational [grading runbook](./runbooks/harbor_grading.md).

---

## How the sites are generated (and why this way)

A **3-stage concept→code pipeline** (design system → page layout → page code), with
generation **stratified across a taxonomy** (10 archetypes × 10 aesthetics × 3
complexity levels; page count scales 5→7→10 with complexity) and a deterministic
**quality gate** at the end (substance floor, static-only enforcement, font-palette
compliance). Rationale and the field research that motivated it:
**[generator_design.md](./design/generator_design.md)** +
**[generator_research.md](./design/research/generator_research.md)** (22 sources, with
the refuted claims listed honestly).

A deliberate fork worth calling out: generation uses **direct Anthropic API calls, not
Claude Code**. Generation is a *data pipeline* (structured in/out, per-stage
temperature control, parallelism, deterministic validation); evaluation is an *agentic
task* (autonomous reasoning, file-writing, iteration). Using the right tool for each
concern is the design choice — the reasoning is in the [thinking trail](./thinking_trail.md).

Scale runs on **Modal** (parallel workers, sealed render image, artifact volume) — see
the [batch-generation runbook](./runbooks/modal_batch.md).

---

## Evaluating the model (and the first real learning)

The eval harness runs **Claude Code + Opus 4.7 ten times** on a task via Harbor on
Modal, grades each attempt, and harvests the results into a per-task visual report
(provenance, score distribution, per-term bars, per-page×term heatmap, and
reference-vs-candidate galleries). Design + decisions:
**[eval_pipeline.md](./design/eval_pipeline.md)**.

The first validated 10× run (reward **0.757 ± 0.011**) surfaced a clean, reproducible
finding:

- **`content` is the bottleneck**, and its fidelity is **inversely proportional to
  prose density** — short labels and big numbers (pricing, index) score ~0.8, dense
  paragraph pages (about, gallery) drop to ~0.40.
- **`color` is near-trivial** (~0.97), so it carries little discriminating signal.
- **`structure` is strong.**

The mechanism: given pixels, not text, the model **paraphrases** copy rather than
transcribing it — its native mode is generation, not OCR. That's arguably *sensible*
behavior the content term penalizes, which raises a genuine design-taste tension worth
surfacing as a learning (is verbatim text the right thing to reward in a *design*
task?). The cross-method agreement (OCR term + the VLM judge) plus the per-page curve
back it up.

---

## How to read this documentation

| Path | What it is |
|---|---|
| [`project-brief.md`](./project-brief.md) | The assignment we built against |
| [`design/`](./design/) | The **why** — grader, generator, and eval-pipeline rationale + the field-research log |
| [`thinking_trail.md`](./thinking_trail.md) | The **raw development trail** — real-time thinking, the bugs hit, the commands run, decisions as they happened |
| [`runbooks/`](./runbooks/) | The **how-to-run** — reproduce a grade (`harbor_grading.md`) or a batch generation (`modal_batch.md`) |
| [`prds/`](./prds/) | The **development arc** — each feature's PRD and the issues it broke into (grader-mvp, site-generator, eval-pipeline), in build order |

Two registers on purpose: `design/` is the polished rationale; `thinking_trail.md` +
`prds/` are the authentic, timestamped trail of how it actually unfolded.

---

## Scope & honesty

- **Part 1 is the focus and is done well** — per the brief's own advice to finish a
  high-taste Part 1 before moving on. **Part 2 (animations)** was then attempted in the
  remaining time as a **rushed prototype** — a deterministic filmstrip grader, a new
  `motion` term, a two-pass generator, and a Modal scaling pipeline, with a perturbation
  ladder proving its reward tracks animation quality — but the research is incomplete
  (a known fixed-6-frame limitation, rougher code), so it is kept *out* of the final
  tasks and lives under [`task2/`](../task2/README.md) with its limitations called out
  honestly. **Part 3 (multiple frameworks: React/Solid/Tailwind)** is designed-for in
  the architecture but not built.
- **Curation of the final ≥10 tasks was manual** (auditable by seed tuple), not an
  algorithmic coverage metric — a deliberate deferral, not an oversight.
- Known limitation by construction: a screenshot is a lossy encoding of long-form copy,
  so some `content` loss is inherent to a screenshot-only replication task — see the
  eval learnings above.
