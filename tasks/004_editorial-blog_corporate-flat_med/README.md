# 004_editorial-blog_corporate-flat_med

**Seed tuple:** `['editorial-blog', 'corporate-flat', 'med', 'students-and-educators', 'warm-and-welcoming']`
**Archetype / Aesthetic / Complexity:** editorial-blog · corporate-flat · med (7 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.787** | 0.793 ± 0.023 | 0.775 | 0.862 |

Per-term means: structure **0.792** · color **0.973** · content **0.673** · design_judge **0.735**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *EduPulse* — an editorial blog / content platform aimed at educators. The
aesthetic is corporate-flat: a friendly teal + burnt-orange palette over peachy-beige
backgrounds with a dark-navy footer, strictly *flat* (no gradients, no shadows, no depth),
pastel circle and rectangle accents behind the hero, clean sans-serif type, and three-column
card grids. Seven pages.

**Why higher reward = better replication.** An editorial blog is prose-dense, so `content`
(0.673) is the binding constraint — and it is also the term a human reader notices first. `color`
is near-ceiling (0.973) and barely moves between trials; the spread (0.775 → 0.862) is driven by
how much real copy each attempt preserves. The best-overall attempt (see [`report.md`](./report.md)
§7) keeps the hero, the "Why EduPulse?" cards, the articles grid, the stats band, the signup
section, and the footer faithful, and carries fuller body text; weaker trials thin the copy out.
Reward orders the trials the way density-of-real-content does.

**What the model struggled with.** The authors page is the worst page for both weak terms. For
`content` ([worst-content candidate vs reference](./images/worst_content_cand.png)) the
reference's dense, paragraph-length author bios and full article-listing metadata collapse into
short, placeholder-like fragments — the model keeps the section skeleton but drops the substance.
For `design_judge` (0.735, [worst-judge candidate](./images/worst_design_judge_cand.png)) the same
page shows looser team-grid spacing, a narrower icon-colour rotation (so the grid reads
monotone), and a lower-contrast sidebar. The agent clearly prioritised getting the layout right
over reproducing the prose — which is exactly the behaviour the `content` term is built to catch.
