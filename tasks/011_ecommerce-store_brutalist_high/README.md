# 011_ecommerce-store_brutalist_high

**Seed tuple:** `['ecommerce-store', 'brutalist', 'high', 'local-community', 'premium-and-understated']`
**Archetype / Aesthetic / Complexity:** ecommerce-store · brutalist · high (10 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.66** | 0.66 ± 0.009 | 0.645 | 0.679 |

Per-term means: structure **0.475** · color **0.963** · content **0.528** · design_judge **0.676**
(weakest term: **structure**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *Local Goods — "Raw Goods for Real People"* — a brutalist e-commerce store for
handmade homegoods/ceramics. The aesthetic is hard brutalism: pure black, cream and warm tan;
heavy all-caps slab headlines; thick horizontal rules and full-width borders; an exposed,
heterogeneous block grid; monospace for dimension labels; no rounded corners anywhere. Ten pages
(home, shop, collections, product detail, about, cart, shipping, faq, contact, reviews).

**Why higher reward = better replication — and where the metric is honestly harsh.** This is the
**lowest-reward task in the set (0.660)** and we included it on purpose: its weakest term is
`structure` (0.475), uniformly low across all ten pages. The home page actually replicates *very*
closely ([best-index candidate vs reference](./images/best_index_cand.png)) — every section is
present, the type/colour/edges read as brutalist. But on the interior pages the architecture is
faithful while the **vertical rhythm drifts**: section heights, padding above headlines, and
spec-table row heights are each off by 10–15px ([worst-structure candidate vs
reference](./images/worst_structure_cand.png)). MS-SSIM compounds those per-section offsets into a
low pixel match. So 0.660 is *fair but strict*: the candidate captured the brutalist identity but
lost the proportional cadence that brutalism actually lives on. This task is the clearest evidence
the grader is **not gameable by surface mimicry** — getting the look right is not the same as
getting the structure right, and the reward says so.

**What the model struggled with.** Beyond structural cadence, `content` is also low (0.528): the
dense product specs and comparison-table copy are paraphrased rather than transcribed. The
takeaway across the ten pages is consistent — the model learned the *vocabulary* of brutalism
(black bars, oversized type, hard edges) but not its *discipline* (grid precision and spacing
proportion), and a layout-sensitive metric is right to dock it.
