# 038_agency-portfolio_luxury-serif_high

**Seed tuple:** `['agency-portfolio', 'luxury-serif', 'high', 'creative-professionals', 'rebellious-and-edgy']`
**Archetype / Aesthetic / Complexity:** agency-portfolio · luxury-serif · high (10 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.743** | 0.741 ± 0.007 | 0.725 | 0.751 |

Per-term means: structure **0.715** · color **0.981** · content **0.537** · design_judge **0.733**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *VANDAL Studio* — a creative agency portfolio with a rebellious streak. The
aesthetic is luxury-serif with an edgy twist: a pure-black canvas, a crimson-red accent (italic
red serif words breaking the headlines), cream body text, ultra-large high-contrast serif display
type, generous whitespace, geometric red accent shapes, and clean grid portfolio layouts. Ten
pages (index, work, case-studies, services, process, about, team, journal, careers, contact).

**Why higher reward = better replication.** `color` is at the ceiling (0.981) — black, cream and
one red are easy to match — so the reward (0.725 → 0.751) is driven down by `content` (0.537, the
second-lowest in the set), and capped further by two layout-side terms: `structure` (0.715, the
**second-lowest structure score in the set** after the brutalist 011) and `design_judge` (0.733).
The best-index attempt is ~90%
faithful ([best-index candidate vs reference](./images/best_index_cand.png)): the serif display,
the italic-red keyword, the red buttons and the dark sectioning all survive, though the whitespace
is slightly pinched. What separates the trials is how much of the agency's *writing* and
*editorial restraint* each one keeps.

**What the model struggled with.** The team page is the worst content page (one trial scores
**0.333**, [candidate vs reference](./images/worst_content_cand.png)): the section headings and
the team members' names are kept, but the individual bios are invented or paraphrased into
boilerplate — the same screenshots-only ceiling that bites every text-heavy page in the set. For
`design_judge`, the contact page ([candidate vs reference](./images/worst_design_judge_cand.png))
trades the luxury-serif restraint for a fussy, form-heavy layout: the form bloats, the generous
whitespace and asymmetric hierarchy collapse, and the editorial grace is lost. `structure` is
squeezed too — on the portfolio **work** page (worst 0.646, [candidate vs
reference](./images/worst_structure_cand.png)) the project-grid columns and gutters drift out of
true, so the gallery loses the crisp editorial alignment the aesthetic leans on. A reviewer sees
the palette and the broad layout are right while the copy is fabricated, the grid wanders, and the
restraint is gone — and the four-term breakdown localises each failure precisely.
