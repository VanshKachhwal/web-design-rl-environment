# EP-03 — Report: harvest job → scores + tables/plots (report items 1–5)

Status: done (committed 8fce10f)

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(grill-resolved, "Report generator (C) — locked v1 contents", items 1–5 +
harvest contract).

## What to build

Point a report command at **any saved Harbor job directory** and get the
scores-and-tables half of a self-contained per-task report — the part that needs
no rendered screenshots, so it is demoable on the **existing `opus47-004` job
today**.

Two pieces, split on the testability seam:

- **Harvest (pure)** — turn a job directory into a **normalized scores object**:
  run metadata from the job result (model, agent, executor, trial count, cost,
  tokens, wall-clock, date); per-trial aggregate `reward` + the four terms, the
  per-page terms, and the judge sub-scores from **each trial's per-trial term
  files**, which are the source of truth (the job-result eval key is dynamic, so
  do not parse the metrics out of it). Persist this as a machine-readable record
  plus a tabular export, written alongside the report. Everything downstream reads
  **only** this object — it is the single contract.
- **Report shell (items 1–5)** — render a single self-contained HTML file from the
  normalized object: (1) a provenance header (task id, seed tuple, model, executor,
  trials, cost/tokens, wall-clock, date, commit); (2) a per-trial score table with a
  summary row (median / mean ± std / min / max); (3) a reward distribution plot plus
  per-term distributions; (4) per-term mean bars with spread; (5) a per-page × per-term
  heatmap. Plots are embedded (no external asset files); matplotlib/HTML assembly is
  the untested shell.

## Acceptance criteria

- [ ] Pointed at a saved job dir, the command writes a normalized scores record
      (machine-readable) + a tabular export + a single self-contained `report.html`.
- [ ] **Harvest is pure and unit-tested** on a fixture job dir: correct per-trial
      `reward` + 4 terms, per-page terms, judge sub-scores, summary stats, and run
      metadata; robust to the dynamic job-result eval key (reads per-trial term files).
- [ ] The **plot-data computations** (distribution series, per-term mean/std, per-page
      × term matrix) are pure and unit-tested on the normalized object.
- [ ] `report.html` renders items 1–5 and is self-contained (opens with no server or
      sibling asset files; images embedded).
- [ ] Verifiable end-to-end on the **existing `opus47-004` job** (no renders required
      for items 1–5).
- [ ] matplotlib/HTML rendering is the untested shell; module import-safe; full suite
      green (clean `TMPDIR`, Docker render test excluded). Prior art: `validate_grader.py`
      (headless Agg plots + committed report) and `grade/study.py` (pure stats helpers).

## Blocked by

- None — can start immediately (demoable on the existing job). Independent of EP-01
  and EP-02.
