# 019_saas-landing_playful-rounded_med

**Seed tuple:** `['saas-landing', 'playful-rounded', 'med', 'local-community', 'premium-and-understated']`
**Archetype / Aesthetic / Complexity:** saas-landing · playful-rounded · med (7 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.793** | 0.789 ± 0.012 | 0.765 | 0.801 |

Per-term means: structure **0.793** · color **0.975** · content **0.695** · design_judge **0.694**
(weakest term: **design_judge**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *Circ* — a team-collaboration SaaS landing site. The aesthetic is playful-rounded:
soft pastels (lavender/periwinkle, mint, coral, soft yellow), pill-shaped buttons, large
border-radius cards, blobby background illustrations, friendly rounded icons, and a rounded sans
type. Seven pages.

**Why higher reward = better replication.** `color` (0.975) and `structure` (0.793) are both high
and steady — the model reliably gets the palette and the layout grid. What moves the reward
(0.765 → 0.801) is `design_judge` (0.694), the weakest term, because the judge is the only term
that scores the *feel* of "playful-rounded" rather than its measurable parts. The best-overall
attempt ([`report.md`](./report.md) §7) keeps the lavender hero, the pill buttons, the rounded
feature cards and the dark stats band — though even there the hero's product-dashboard mockup
loses fine line-weight detail. Reward tracks how much of the bouncy, saturated character each
attempt retains.

**What the model struggled with.** On the integrations page ([worst-judge candidate vs
reference](./images/worst_design_judge_cand.png)) the *rounding* survives — the radii and pill
shapes are intact — but the **playfulness drains out**: the pastels desaturate, contrast drops,
and the rounded cards stop popping against the background, so the page reads muted and corporate
instead of warm and friendly. That is a genuinely subtle miss — the geometry is right and the
palette is *almost* right — which is exactly why it lands on `design_judge` rather than on `color`
or `structure`. (Body copy is largely preserved here, so `content` at 0.695 is not the story; the
aesthetic feel is.) This task shows the VLM judge earning its place: it catches a degradation the
pixel/colour metrics miss.
