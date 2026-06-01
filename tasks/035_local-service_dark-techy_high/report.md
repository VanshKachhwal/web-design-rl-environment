# Model-eval report — opus47-035

## 1. Provenance

| field | value |
|---|---|
| Task | opus47-035 |
| Seed tuple | local-service / dark-techy / high / local-community / premium-and-understated |
| Archetype / Aesthetic / Complexity | local-service / dark-techy / high |
| Model | claude-opus-4-7 |
| Agent | claude-code |
| Executor | modal |
| Trials | 10 |
| Cost | $31.97 |
| Wall-clock | 21.5 min |
| Date | 2026-05-31 |
| Repo commit | fd7c5311b6ae7fbe07c534662a9b313d1a6931f7 |

## 2. Per-trial scores

| trial | reward | structure | color | content | design_judge |
|---|---|---|---|---|---|
| 3M4CAXn | 0.747 | 0.774 | 0.974 | 0.545 | 0.695 |
| BraKtNp | 0.738 | 0.766 | 0.977 | 0.523 | 0.688 |
| KbwY6JH | 0.752 | 0.782 | 0.978 | 0.563 | 0.685 |
| NCSn9vP | 0.743 | 0.724 | 0.982 | 0.555 | 0.713 |
| S2ywVEC | 0.716 | 0.667 | 0.971 | 0.551 | 0.675 |
| WXnEkTs | 0.719 | 0.698 | 0.966 | 0.563 | 0.647 |
| h9QcJ6D | 0.738 | 0.727 | 0.977 | 0.551 | 0.698 |
| isoBE3J | 0.720 | 0.706 | 0.975 | 0.521 | 0.677 |
| sjat758 | 0.746 | 0.763 | 0.991 | 0.529 | 0.703 |
| v8hWxPH | 0.739 | 0.771 | 0.976 | 0.539 | 0.670 |
| **summary** | med 0.739 · 0.736±0.012 | med 0.745 · 0.738±0.037 | med 0.976 · 0.977±0.006 | med 0.548 · 0.544±0.015 | med 0.686 · 0.685±0.018 |

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)

## 6. Worst per metric (reference vs candidate)

**structure** — worst page `reviews` (trial `S2ywVEC`, score 0.623)

| reference | candidate |
|---|---|
| ![reference](images/worst_structure_ref.png) | ![candidate](images/worst_structure_cand.png) |

**color** — worst page `gallery` (trial `BraKtNp`, score 0.954)

| reference | candidate |
|---|---|
| ![reference](images/worst_color_ref.png) | ![candidate](images/worst_color_cand.png) |

**content** — worst page `faq` (trial `BraKtNp`, score 0.326)

| reference | candidate |
|---|---|
| ![reference](images/worst_content_ref.png) | ![candidate](images/worst_content_cand.png) |

**design_judge** — worst page `about` (trial `v8hWxPH`, score 0.550)

| reference | candidate |
|---|---|
| ![reference](images/worst_design_judge_ref.png) | ![candidate](images/worst_design_judge_cand.png) |


## 7. Best-overall attempt vs reference (all pages)

Best-overall trial `KbwY6JH` (reward 0.752).

| page | reference | candidate |
|---|---|---|
| index | ![reference index](images/best_index_ref.png) | ![candidate index](images/best_index_cand.png) |
| services | ![reference services](images/best_services_ref.png) | ![candidate services](images/best_services_cand.png) |
| pricing | ![reference pricing](images/best_pricing_ref.png) | ![candidate pricing](images/best_pricing_cand.png) |
| about | ![reference about](images/best_about_ref.png) | ![candidate about](images/best_about_cand.png) |
| contact | ![reference contact](images/best_contact_ref.png) | ![candidate contact](images/best_contact_cand.png) |
| areas | ![reference areas](images/best_areas_ref.png) | ![candidate areas](images/best_areas_cand.png) |
| gallery | ![reference gallery](images/best_gallery_ref.png) | ![candidate gallery](images/best_gallery_cand.png) |
| reviews | ![reference reviews](images/best_reviews_ref.png) | ![candidate reviews](images/best_reviews_cand.png) |
| booking | ![reference booking](images/best_booking_ref.png) | ![candidate booking](images/best_booking_cand.png) |
| faq | ![reference faq](images/best_faq_ref.png) | ![candidate faq](images/best_faq_cand.png) |
