# Model-eval report — 038_agency-portfolio_luxury-serif_high

## 1. Provenance

| field | value |
|---|---|
| Task | 038_agency-portfolio_luxury-serif_high |
| Seed tuple | agency-portfolio / luxury-serif / high / creative-professionals / rebellious-and-edgy |
| Archetype / Aesthetic / Complexity | agency-portfolio / luxury-serif / high |
| Model | claude-opus-4-7 |
| Agent | claude-code |
| Executor | modal |
| Trials | 10 |
| Cost | $32.26 |
| Wall-clock | 20.5 min |
| Date | 2026-06-01 |
| Repo commit | fd7c5311b6ae7fbe07c534662a9b313d1a6931f7 |

## 2. Per-trial scores

| trial | reward | structure | color | content | design_judge |
|---|---|---|---|---|---|
| 2JsBHaS | 0.751 | 0.736 | 0.986 | 0.534 | 0.750 |
| 3wH5V5x | 0.734 | 0.708 | 0.973 | 0.539 | 0.715 |
| 9hYxY8a | 0.747 | 0.720 | 0.985 | 0.559 | 0.722 |
| D3R9oFB | 0.742 | 0.699 | 0.983 | 0.537 | 0.750 |
| HufxrKX | 0.740 | 0.714 | 0.980 | 0.529 | 0.738 |
| KACxe2y | 0.744 | 0.732 | 0.983 | 0.537 | 0.725 |
| NDo6buR | 0.749 | 0.714 | 0.982 | 0.557 | 0.742 |
| QLcPvzE | 0.744 | 0.726 | 0.982 | 0.542 | 0.725 |
| cwRa77U | 0.737 | 0.707 | 0.976 | 0.517 | 0.747 |
| gGvA7Tt | 0.725 | 0.690 | 0.982 | 0.518 | 0.713 |
| **summary** | med 0.743 · 0.741±0.007 | med 0.714 · 0.715±0.014 | med 0.982 · 0.981±0.004 | med 0.537 · 0.537±0.013 | med 0.731 · 0.733±0.014 |

## 3. Reward + per-term distributions

![reward and per-term distributions](distributions.png)

## 4. Per-term means

![per-term mean bars](per_term_means.png)

## 5. Per-page × per-term heatmap

![per-page per-term heatmap](heatmap.png)

## 6. Worst per metric (reference vs candidate)

**structure** — worst page `work` (trial `gGvA7Tt`, score 0.646)

| reference | candidate |
|---|---|
| ![reference](images/worst_structure_ref.png) | ![candidate](images/worst_structure_cand.png) |

**color** — worst page `work` (trial `gGvA7Tt`, score 0.960)

| reference | candidate |
|---|---|
| ![reference](images/worst_color_ref.png) | ![candidate](images/worst_color_cand.png) |

**content** — worst page `team` (trial `HufxrKX`, score 0.333)

| reference | candidate |
|---|---|
| ![reference](images/worst_content_ref.png) | ![candidate](images/worst_content_cand.png) |

**design_judge** — worst page `contact` (trial `QLcPvzE`, score 0.625)

| reference | candidate |
|---|---|
| ![reference](images/worst_design_judge_ref.png) | ![candidate](images/worst_design_judge_cand.png) |


## 7. Best-overall attempt vs reference (all pages)

Best-overall trial `2JsBHaS` (reward 0.751).

| page | reference | candidate |
|---|---|---|
| index | ![reference index](images/best_index_ref.png) | ![candidate index](images/best_index_cand.png) |
| work | ![reference work](images/best_work_ref.png) | ![candidate work](images/best_work_cand.png) |
| case-studies | ![reference case-studies](images/best_case-studies_ref.png) | ![candidate case-studies](images/best_case-studies_cand.png) |
| services | ![reference services](images/best_services_ref.png) | ![candidate services](images/best_services_cand.png) |
| process | ![reference process](images/best_process_ref.png) | ![candidate process](images/best_process_cand.png) |
| about | ![reference about](images/best_about_ref.png) | ![candidate about](images/best_about_cand.png) |
| team | ![reference team](images/best_team_ref.png) | ![candidate team](images/best_team_cand.png) |
| journal | ![reference journal](images/best_journal_ref.png) | ![candidate journal](images/best_journal_cand.png) |
| careers | ![reference careers](images/best_careers_ref.png) | ![candidate careers](images/best_careers_cand.png) |
| contact | ![reference contact](images/best_contact_ref.png) | ![candidate contact](images/best_contact_cand.png) |
