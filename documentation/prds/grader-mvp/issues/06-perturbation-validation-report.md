# 06 — Perturbation harness + validation study + report

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

The evidence that "higher reward = better replication." A perturbation module that degrades a
reference in **ordered** steps along controlled axes — image-space (color drift, blur,
spatial shift, region occlusion, noise) and a few **re-rendered source** edits (remove an
element, swap a font, shift the CSS palette, delete text) — plus degenerate generators
(blank, solid-color, lorem-ipsum). A validation study runs the full grader across the
perturbation ladder and the degenerate set and checks:

- each metric is monotonic on its own axis (color term responds to color drift, etc.),
- the aggregate reward is monotonic vs perturbation severity (rank correlation),
- the ground-truth oracle scores ≈ 1.0 and degenerate outputs score at the floor.

Emit a **committed visual report** (reward vs severity curves, per-metric curves,
floor/ceiling anchors) plus the raw study data, so the evidence is shareable on the public
GitHub repo. Extend the hand-made fixture to a 5-page site for the multi-page aggregation
check.

## Acceptance criteria

- [ ] Perturbation generators produce severity-ordered variants (image + re-rendered source) and the degenerate set.
- [ ] Study computes per-metric and aggregate monotonicity (rank correlation, e.g. Spearman/Kendall) against known severity.
- [ ] Oracle (unperturbed reference) scores ≈ 1.0; blank/solid/lorem score at the floor.
- [ ] A 5-page fixture exercises multi-page aggregation (degrading one page lowers the site reward).
- [ ] **The report is persisted (committed) under `reports/grader-validation/`**, containing:
  - [ ] PNG/SVG graphs: `reward_vs_severity`, per-metric curves, floor/ceiling anchors, multi-page aggregation.
  - [ ] A `README.md` that embeds those images and states the quantitative results next to them — rank-correlation numbers, oracle score, degenerate floor scores, and the documented `color ≈ 0.67` mean-gray per-axis caveat (the aggregate, not `color` alone, floors that case).
  - [ ] The raw per-variant scores as CSV and/or JSON, so the curves are reproducible and the numbers auditable.
- [ ] A runnable entry point (`scripts/validate_grader.py`) regenerates the whole report from scratch.
- [ ] Tests cover that perturbation levels are correctly severity-ordered and degenerate generators score at the floor.

## Notes

- Plotting needs `matplotlib` (add to deps; Python 3.14 wheels exist).
- Image-space perturbations stress each metric directly; re-rendered source perturbations
  add realism. Degenerate floors (blank/solid/lorem) prove anti-gaming on the **aggregate**.
- This is a graded deliverable: a reviewer should be convinced by the committed
  `reports/grader-validation/README.md` alone (picture for intuition, table for proof).

## Blocked by

- Issue 02 (`color`), Issue 03 (`content`), Issue 04 (`design_judge`), Issue 05 (live render).

## Comments

- **Done (2026-05-30), committed `fb3f8fd`.** 59 tests pass (+18). Report committed at
  `reports/grader-validation/` (generated with the **real** Anthropic judge).
- **Evidence:** aggregate reward Spearman ρ = −1.000 vs severity (pairwise acc 1.00);
  per-metric all ≈−1.0 (`remove_element` −0.956); oracle = 1.000; 5-page → 1.000 then 0.908
  with one page degraded.
- **Finding (research-taste material):** degenerate floor is ~0.4 (blank 0.426 / solid-gray
  0.343 / lorem 0.433), NOT ~0 — a blank white page scores `structure`=0.70, `color`=1.00
  because the reference is mostly white background. The aggregate still floors it via
  `content`+`design_judge`. Honest mild gaming surface; candidate motivation for a coverage
  penalty / weight revisit later.
- `_work/` scratch dir gitignored; `matplotlib` added to deps.
