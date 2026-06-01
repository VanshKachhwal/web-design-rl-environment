# Model-eval report — 011_ecommerce-store_brutalist_high

## 1. Provenance

| field | value |
|---|---|
| Task | 011_ecommerce-store_brutalist_high |
| Seed tuple | ecommerce-store / brutalist / high / local-community / premium-and-understated |
| Archetype / Aesthetic / Complexity | ecommerce-store / brutalist / high |
| Model | claude-opus-4-7 |
| Agent | claude-code |
| Executor | modal |
| Trials | 10 |
| Cost | $36.10 |
| Wall-clock | 21.1 min |
| Date | 2026-06-01 |
| Repo commit | fd7c5311b6ae7fbe07c534662a9b313d1a6931f7 |

## 2. Per-trial scores

| trial | reward | structure | color | content | design_judge |
|---|---|---|---|---|---|
| 47zEvfx | 0.660 | 0.458 | 0.959 | 0.544 | 0.677 |
| 6RgEQpD | 0.673 | 0.498 | 0.967 | 0.543 | 0.682 |
| M86CyR8 | 0.649 | 0.455 | 0.957 | 0.491 | 0.693 |
| UDXH7VK | 0.645 | 0.475 | 0.955 | 0.484 | 0.665 |
| WtujNSA | 0.662 | 0.472 | 0.973 | 0.535 | 0.667 |
| ao9DK5V | 0.663 | 0.474 | 0.967 | 0.562 | 0.647 |
| iFEU45r | 0.679 | 0.487 | 0.963 | 0.573 | 0.693 |
| jHKbtVS | 0.656 | 0.478 | 0.957 | 0.501 | 0.690 |
| xLNpcQp | 0.657 | 0.464 | 0.963 | 0.519 | 0.680 |
| yxemSMH | 0.661 | 0.488 | 0.965 | 0.526 | 0.665 |
| **summary** | med 0.660 · 0.660±0.009 | med 0.475 · 0.475±0.013 | med 0.963 · 0.963±0.005 | med 0.531 · 0.528±0.028 | med 0.679 · 0.676±0.014 |

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)

## 6. Worst per metric (reference vs candidate)

**structure** — worst page `product` (trial `47zEvfx`, score 0.378)

| reference | candidate |
|---|---|
| ![reference](images/worst_structure_ref.png) | ![candidate](images/worst_structure_cand.png) |

**color** — worst page `reviews` (trial `47zEvfx`, score 0.939)

| reference | candidate |
|---|---|
| ![reference](images/worst_color_ref.png) | ![candidate](images/worst_color_cand.png) |

**content** — worst page `collections` (trial `47zEvfx`, score 0.272)

| reference | candidate |
|---|---|
| ![reference](images/worst_content_ref.png) | ![candidate](images/worst_content_cand.png) |

**design_judge** — worst page `faq` (trial `WtujNSA`, score 0.425)

| reference | candidate |
|---|---|
| ![reference](images/worst_design_judge_ref.png) | ![candidate](images/worst_design_judge_cand.png) |


## 7. Best-overall attempt vs reference (all pages)

Best-overall trial `iFEU45r` (reward 0.679).

| page | reference | candidate |
|---|---|---|
| index | ![reference index](images/best_index_ref.png) | ![candidate index](images/best_index_cand.png) |
| shop | ![reference shop](images/best_shop_ref.png) | ![candidate shop](images/best_shop_cand.png) |
| product | ![reference product](images/best_product_ref.png) | ![candidate product](images/best_product_cand.png) |
| collections | ![reference collections](images/best_collections_ref.png) | ![candidate collections](images/best_collections_cand.png) |
| cart | ![reference cart](images/best_cart_ref.png) | ![candidate cart](images/best_cart_cand.png) |
| about | ![reference about](images/best_about_ref.png) | ![candidate about](images/best_about_cand.png) |
| reviews | ![reference reviews](images/best_reviews_ref.png) | ![candidate reviews](images/best_reviews_cand.png) |
| shipping | ![reference shipping](images/best_shipping_ref.png) | ![candidate shipping](images/best_shipping_cand.png) |
| faq | ![reference faq](images/best_faq_ref.png) | ![candidate faq](images/best_faq_cand.png) |
| contact | ![reference contact](images/best_contact_ref.png) | ![candidate contact](images/best_contact_cand.png) |
