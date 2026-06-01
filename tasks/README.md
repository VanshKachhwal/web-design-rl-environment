# Final tasks — web-design replication RL environment

Eleven curated tasks selected to **showcase the distribution and complexity** of the
pipeline's output (per the project brief). Each folder is a self-contained bundle:

- `task/` — the runnable Harbor task (reference screenshots in `environment/reference/`,
  the baked grader in `tests/`, `task.toml`).
- `report.md` — the visual report of Claude Code + Opus 4.7 run **10×** on the task
  (renders inline on GitHub; plots + reference-vs-candidate galleries ship as PNG
  files alongside it).
- `scores.json` / `scores.csv` — the normalized per-trial score contract.
- `README.md` — per-task narrative.

## The 11 tasks

| id | archetype | aesthetic | cx | pages | median reward | min–max |
|---|---|---|---|---|---|---|
| 000 | saas-landing | swiss-editorial | low | 5 | **0.827** ⬆ highest | 0.815–0.839 |
| 004 | editorial-blog | corporate-flat | med | 7 | **0.787** | 0.775–0.862 |
| 007 | event-conference | retro-y2k | med | 7 | **0.727** | 0.703–0.836 |
| 011 | ecommerce-store | brutalist | high | 10 | **0.66** ⬇ lowest | 0.645–0.679 |
| 012 | restaurant-hospitality | neo-brutalist | low | 5 | **0.775** | 0.749–0.782 |
| 015 | personal-resume | dark-techy | low | 5 | **0.798** | 0.792–0.801 |
| 019 | saas-landing | playful-rounded | med | 7 | **0.793** | 0.765–0.801 |
| 023 | nonprofit-civic | glassmorphism | high | 10 | **0.781** | 0.776–0.788 |
| 035 | local-service | dark-techy | high | 10 | **0.739** | 0.716–0.752 |
| 036 | docs-product | warm-organic | low | 5 | **0.792** | 0.769–0.809 |
| 038 | agency-portfolio | luxury-serif | high | 10 | **0.743** | 0.725–0.751 |

## Coverage

- **Archetypes (10):** agency-portfolio, docs-product, ecommerce-store, editorial-blog, event-conference, local-service, nonprofit-civic, personal-resume, restaurant-hospitality, saas-landing
- **Aesthetics (10):** brutalist, corporate-flat, dark-techy, glassmorphism, luxury-serif, neo-brutalist, playful-rounded, retro-y2k, swiss-editorial, warm-organic
- **Complexity:** 4 × high (10-page), 3 × med (7-page), 4 × low (5-page)
- **Score range:** 0.66 → 0.827 (median reward), both extremes included

> Note: the CSS-only / no-image-asset constraint shows as neutral placeholder blocks in
> the renders — deliberate, so tasks stay hermetic and reproducible. `local-service`
> (035) uses the clean `opus47-035` eval run, renamed to its canonical seed name.

## How to use

**View a report** — open `report.md` on GitHub (renders inline), or locally:

```bash
open tasks/000_saas-landing_swiss-editorial_low/report.md
```

**Re-run a task** (Claude Code + Opus 4.7 ×10, via the eval launcher):

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate.py \
    --task tasks/000_saas-landing_swiss-editorial_low/task --name my-eval --yes
```

See [`documentation/`](../documentation/) for how the grader, generator, and eval
pipeline were designed and validated.
