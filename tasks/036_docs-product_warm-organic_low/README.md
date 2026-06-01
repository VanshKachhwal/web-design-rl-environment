# 036_docs-product_warm-organic_low

**Seed tuple:** `['docs-product', 'warm-organic', 'low', 'students-and-educators', 'warm-and-welcoming']`
**Archetype / Aesthetic / Complexity:** docs-product · warm-organic · low (5 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.792** | 0.79 ± 0.012 | 0.769 | 0.809 |

Per-term means: structure **0.768** · color **0.963** · content **0.69** · design_judge **0.74**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *Seedling* — a documentation site for a software product. The aesthetic is
warm-organic: a terracotta / sage / cream / brown palette, a Playfair Display serif paired with
Work Sans and Space Grotesk (and JetBrains Mono for code), soft rounded corners, and organic
blob/pastel decorations. Five pages (index, guides, reference, examples, support).

**Why higher reward = better replication.** `color` (0.963) is high and steady, so the reward
(0.769 → 0.809) is set by `content` (0.69, weakest) and `design_judge` (0.74) — the terms that
matter most for a docs site, which is text- and code-dense by nature. The best-index attempt is
~90% faithful ([best-index candidate vs reference](./images/best_index_cand.png)): the colour
blocks, button styles, feature grid and blob decorations all land. The reward gap between trials
is about how much of the *documentation substance* each one keeps.

**What the model struggled with.** The reference page is the worst content page (one trial scores
**0.271**, [candidate vs reference](./images/worst_content_cand.png)): the dense design-token
tables, hex codes, CSS code blocks and type-scale listings are dropped or summarised down to a
handful of colour swatches and font cards — the candidate reproduces the *look* of a reference
page without its *contents*, losing roughly 70% of the text. For `design_judge`, the guides page
([candidate vs reference](./images/worst_design_judge_cand.png)) flattens: the icon-colour
variation and card differentiation that signal the deliberate warm-organic styling weaken into a
more generic template. This bundle is the demonstration that the `content` term catches dropped
documentation — exactly the failure a pixel- or colour-only grader would wave through.
