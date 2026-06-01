# 012_restaurant-hospitality_neo-brutalist_low

**Seed tuple:** `['restaurant-hospitality', 'neo-brutalist', 'low', 'students-and-educators', 'warm-and-welcoming']`
**Archetype / Aesthetic / Complexity:** restaurant-hospitality · neo-brutalist · low (5 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.775** | 0.769 ± 0.012 | 0.749 | 0.782 |

Per-term means: structure **0.718** · color **0.96** · content **0.685** · design_judge **0.713**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *The Story Hall* — a neo-brutalist restaurant site. The aesthetic pairs thick
black borders and hard, offset *solid* drop-shadows with a warm flat palette (golden yellow, rust
orange, forest green, charcoal, cream), chunky sans-serif headings, and playful sticker-style
badges. Five pages (index, menu, about, contact, reservations).

**Why higher reward = better replication.** `color` is near-ceiling (0.96) and stable, so the
trial-to-trial reward (0.749 → 0.782) is set by `content` (0.685) and `design_judge` (0.713) — the
two places the eye actually lands. The best-overall attempt ([`report.md`](./report.md) §7) keeps
the yellow hero, the bordered "why dine with us" cards, the rust CTA band, the offset-shadow
testimonial cards, and the green signup section faithful. Higher-reward trials are the ones that
hold both the menu copy *and* the hard-shadow vigour; the ranking matches a side-by-side eyeball.

**What the model struggled with.** The menu page is the worst page for both weak terms. For
`content` ([worst-content candidate vs reference](./images/worst_content_cand.png)) the dish names
survive but the one-to-two-line descriptions under each item are gutted — the page keeps its shape
and loses its substance. For `design_judge` ([worst-judge candidate](./images/worst_design_judge_cand.png))
the signature neo-brutalist punch is diluted: the hard black offset shadows soften to light grey,
the borders thin out, and the badge yellows desaturate, so the page reads more "tasteful modern"
than "neo-brutalist". The per-trial reward still orders by overall fidelity — but it is the menu
page, not the strong home page, that decides where each attempt lands.
