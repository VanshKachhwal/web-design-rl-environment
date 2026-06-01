# 000_saas-landing_swiss-editorial_low

**Seed tuple:** `['saas-landing', 'swiss-editorial', 'low', 'north-american-consumers', 'confident-and-bold']`
**Archetype / Aesthetic / Complexity:** saas-landing · swiss-editorial · low (5 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.827** | 0.828 ± 0.007 | 0.815 | 0.839 |

Per-term means: structure **0.781** · color **0.99** · content **0.775** · design_judge **0.765**
(weakest term: **design_judge**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *GridLine* — a SaaS landing page for a design-system / component-library
product. The aesthetic is textbook Swiss-editorial: a near-monochrome palette (one cobalt-blue
accent over charcoal and off-white), heavy geometric all-caps display type set against small,
refined body copy, a strict left-aligned grid, generous whitespace, thin dividing rules, and an
asymmetric hero (headline left, product mockup right). Five pages — index, features, pricing,
about, contact.

**Why higher reward = better replication.** `color` sits at the ceiling (0.99) on every trial,
because the palette is tiny and flat — so it does *not* separate the attempts. The whole reward
spread (0.815 → 0.839) is carried by `structure`, `content`, and `design_judge` — exactly the
terms where the eye sees a difference. The best-overall trial (`gfEyC5b`, 0.839; see
[`report.md`](./report.md) §7) reproduces the hero, the three-column feature grid, the black
stats bar, the blue CTA band, and the footer in near-correct proportion; the lower trials drift
on section rhythm and rewrite copy. The grader's ranking is the one you would pick by eye.

**What the model struggled with.** `design_judge` is the weakest term (0.765). On the features
page ([worst-judge candidate vs reference](./images/worst_design_judge_cand.png)) the reference's
alternating, mixed-size editorial grid regularises into evenly-sized blocks and the type
hierarchy flattens — the Swiss tension between huge display and tiny body softens into something
more ordinary. `content` is a hair behind (0.775): the index worst-trial drops to **0.417**
([worst-content candidate](./images/worst_content_cand.png)) because the headline and feature
copy are rewritten into generic SaaS boilerplate. Tellingly, the *structured* short text on
pricing/about still scores 0.9+ — the loss is concentrated in the prose-y marketing lines the
model paraphrases instead of transcribing verbatim.
