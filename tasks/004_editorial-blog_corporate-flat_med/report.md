# Model-eval report — 004_editorial-blog_corporate-flat_med

## 1. Provenance

| field | value |
|---|---|
| Task | 004_editorial-blog_corporate-flat_med |
| Seed tuple | editorial-blog / corporate-flat / med / students-and-educators / warm-and-welcoming |
| Archetype / Aesthetic / Complexity | editorial-blog / corporate-flat / med |
| Model | claude-opus-4-7 |
| Agent | claude-code |
| Executor | modal |
| Trials | 10 |
| Cost | $29.29 |
| Wall-clock | 23.4 min |
| Date | 2026-05-31 |
| Repo commit | fd7c5311b6ae7fbe07c534662a9b313d1a6931f7 |

## 2. Per-trial scores

| trial | reward | structure | color | content | design_judge |
|---|---|---|---|---|---|
| 5gDVnG7 | 0.862 | 0.794 | 0.978 | 0.849 | 0.829 |
| DroJgBS | 0.787 | 0.776 | 0.968 | 0.682 | 0.721 |
| EcRwc7R | 0.787 | 0.802 | 0.978 | 0.648 | 0.721 |
| HMwojm2 | 0.787 | 0.796 | 0.969 | 0.652 | 0.732 |
| LyHJTwm | 0.786 | 0.792 | 0.971 | 0.663 | 0.718 |
| ZTWNYYr | 0.790 | 0.793 | 0.968 | 0.668 | 0.732 |
| fp5PyXL | 0.775 | 0.788 | 0.973 | 0.634 | 0.707 |
| hscGHTb | 0.780 | 0.792 | 0.972 | 0.637 | 0.721 |
| idW2QXR | 0.787 | 0.795 | 0.977 | 0.637 | 0.739 |
| y2bm8AT | 0.788 | 0.791 | 0.974 | 0.661 | 0.725 |
| **summary** | med 0.787 · 0.793±0.023 | med 0.793 · 0.792±0.006 | med 0.972 · 0.973±0.004 | med 0.656 · 0.673±0.060 | med 0.723 · 0.735±0.032 |

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)

## 6. Worst per metric (reference vs candidate)

**structure** — worst page `authors` (trial `DroJgBS`, score 0.739)

| reference | candidate |
|---|---|
| ![reference](images/worst_structure_ref.png) | ![candidate](images/worst_structure_cand.png) |

**color** — worst page `featured` (trial `HMwojm2`, score 0.945)

| reference | candidate |
|---|---|
| ![reference](images/worst_color_ref.png) | ![candidate](images/worst_color_cand.png) |

**content** — worst page `authors` (trial `idW2QXR`, score 0.431)

| reference | candidate |
|---|---|
| ![reference](images/worst_content_ref.png) | ![candidate](images/worst_content_cand.png) |

**design_judge** — worst page `authors` (trial `hscGHTb`, score 0.575)

| reference | candidate |
|---|---|
| ![reference](images/worst_design_judge_ref.png) | ![candidate](images/worst_design_judge_cand.png) |


## 7. Best-overall attempt vs reference (all pages)

Best-overall trial `5gDVnG7` (reward 0.862).

| page | reference | candidate |
|---|---|---|
| index | ![reference index](images/best_index_ref.png) | ![candidate index](images/best_index_cand.png) |
| articles | ![reference articles](images/best_articles_ref.png) | ![candidate articles](images/best_articles_cand.png) |
| topics | ![reference topics](images/best_topics_ref.png) | ![candidate topics](images/best_topics_cand.png) |
| featured | ![reference featured](images/best_featured_ref.png) | ![candidate featured](images/best_featured_cand.png) |
| authors | ![reference authors](images/best_authors_ref.png) | ![candidate authors](images/best_authors_cand.png) |
| about | ![reference about](images/best_about_ref.png) | ![candidate about](images/best_about_cand.png) |
| contact | ![reference contact](images/best_contact_ref.png) | ![candidate contact](images/best_contact_cand.png) |
