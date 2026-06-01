# Model-eval report — 019_saas-landing_playful-rounded_med

## 1. Provenance

| field | value |
|---|---|
| Task | 019_saas-landing_playful-rounded_med |
| Seed tuple | saas-landing / playful-rounded / med / local-community / premium-and-understated |
| Archetype / Aesthetic / Complexity | saas-landing / playful-rounded / med |
| Model | claude-opus-4-7 |
| Agent | claude-code |
| Executor | modal |
| Trials | 10 |
| Cost | $22.33 |
| Wall-clock | 16.1 min |
| Date | 2026-06-01 |
| Repo commit | fd7c5311b6ae7fbe07c534662a9b313d1a6931f7 |

## 2. Per-trial scores

| trial | reward | structure | color | content | design_judge |
|---|---|---|---|---|---|
| 72asDxZ | 0.800 | 0.805 | 0.972 | 0.731 | 0.693 |
| LQH4vp7 | 0.795 | 0.794 | 0.976 | 0.707 | 0.704 |
| MPrwRB5 | 0.798 | 0.798 | 0.976 | 0.720 | 0.696 |
| MdSego7 | 0.765 | 0.776 | 0.970 | 0.644 | 0.671 |
| Q8kF9GB | 0.786 | 0.794 | 0.975 | 0.689 | 0.686 |
| RtQUVPT | 0.786 | 0.781 | 0.972 | 0.677 | 0.714 |
| XHwxNcB | 0.772 | 0.786 | 0.981 | 0.627 | 0.693 |
| eJxPX9H | 0.790 | 0.786 | 0.973 | 0.714 | 0.689 |
| gddxyCa | 0.800 | 0.804 | 0.978 | 0.709 | 0.707 |
| wbmycsL | 0.801 | 0.809 | 0.977 | 0.730 | 0.689 |
| **summary** | med 0.793 · 0.789±0.012 | med 0.794 · 0.793±0.010 | med 0.976 · 0.975±0.003 | med 0.708 · 0.695±0.034 | med 0.693 · 0.694±0.011 |

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)

## 6. Worst per metric (reference vs candidate)

**structure** — worst page `customers` (trial `MdSego7`, score 0.749)

| reference | candidate |
|---|---|
| ![reference](images/worst_structure_ref.png) | ![candidate](images/worst_structure_cand.png) |

**color** — worst page `customers` (trial `MdSego7`, score 0.952)

| reference | candidate |
|---|---|
| ![reference](images/worst_color_ref.png) | ![candidate](images/worst_color_cand.png) |

**content** — worst page `about` (trial `eJxPX9H`, score 0.422)

| reference | candidate |
|---|---|
| ![reference](images/worst_content_ref.png) | ![candidate](images/worst_content_cand.png) |

**design_judge** — worst page `integrations` (trial `MdSego7`, score 0.550)

| reference | candidate |
|---|---|
| ![reference](images/worst_design_judge_ref.png) | ![candidate](images/worst_design_judge_cand.png) |


## 7. Best-overall attempt vs reference (all pages)

Best-overall trial `wbmycsL` (reward 0.801).

| page | reference | candidate |
|---|---|---|
| index | ![reference index](images/best_index_ref.png) | ![candidate index](images/best_index_cand.png) |
| features | ![reference features](images/best_features_ref.png) | ![candidate features](images/best_features_cand.png) |
| pricing | ![reference pricing](images/best_pricing_ref.png) | ![candidate pricing](images/best_pricing_cand.png) |
| integrations | ![reference integrations](images/best_integrations_ref.png) | ![candidate integrations](images/best_integrations_cand.png) |
| customers | ![reference customers](images/best_customers_ref.png) | ![candidate customers](images/best_customers_cand.png) |
| about | ![reference about](images/best_about_ref.png) | ![candidate about](images/best_about_cand.png) |
| contact | ![reference contact](images/best_contact_ref.png) | ![candidate contact](images/best_contact_cand.png) |
