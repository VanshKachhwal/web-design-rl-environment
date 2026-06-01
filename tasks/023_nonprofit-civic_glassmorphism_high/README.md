# 023_nonprofit-civic_glassmorphism_high

**Seed tuple:** `['nonprofit-civic', 'glassmorphism', 'high', 'health-and-wellness-seekers', 'nostalgic-and-charming']`
**Archetype / Aesthetic / Complexity:** nonprofit-civic · glassmorphism · high (10 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.781** | 0.78 ± 0.004 | 0.776 | 0.788 |

Per-term means: structure **0.816** · color **0.976** · content **0.655** · design_judge **0.675**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *Wellspring* — a health-and-wellness nonprofit / civic org. The aesthetic is
glassmorphism: frosted translucent cards with backdrop blur, soft pink-to-blue gradient
backgrounds, teal/sage accents, a serif display paired with a sans body, and layered, low-contrast
depth. Ten pages (index, mission, programs, donate, impact, volunteer, events, news, partners,
contact).

**Why higher reward = better replication — and the structure/content split is visible.** This
bundle posts the **highest `structure` score in the set (0.816) despite being a 10-page site.**
That is earned, not lucky: the page architecture is rigid and modular (hero → stat band → 3×2
program-card grid → CTA → footer), grid geometry is tractable, and the glass effect itself is
lightweight CSS (opacity + `backdrop-filter`) rather than something generative. The best-index
attempt is near-identical to the reference ([best-index candidate vs reference](./images/best_index_cand.png)).
And yet reward is only 0.781 — because the grader's *other* terms catch what `structure` cannot.
This task is a clean demonstration that the four terms decompose a result: layout right, texture
and substance thin.

**What the model struggled with.** The events page is the worst page for both weak terms. For
`content` (worst **0.451**, [candidate vs reference](./images/worst_content_cand.png)) the
distinct workshop titles and descriptions degrade into generic/placeholder card labels — the
program narrative goes hollow. For `design_judge` (worst 0.575, [candidate vs
reference](./images/worst_design_judge_cand.png)) the frosted translucency flattens into *opaque*
flat-pastel cards: the blur and soft shadows drop, and the glassmorphism illusion — the whole
point of the aesthetic — collapses to plain colour blocks. A reviewer sees instantly that the
skeleton is correct while the glass and the copy are missing; the grader's term breakdown says the
same thing in numbers.
