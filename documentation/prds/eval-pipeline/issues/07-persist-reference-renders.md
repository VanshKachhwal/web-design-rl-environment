# EP-07 — Persist the grade-time reference renders + source the report from them

Status: done

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md` (the
visual-evidence galleries, items 6–7). The symmetric twin of EP-01 (which persists
the *candidate* renders) for the *reference* side.

## Problem

The report's item 6/7 galleries show the candidate render but the **reference column
is blank**. Root cause: the reference screenshots the grader compares against are
rendered from the reference HTML into a **`TemporaryDirectory` inside the verifier
and discarded** when grading finishes (`grade/__main__.py` `_resolve_reference`,
`--reference-site` mode). EP-01 persists the candidate renders to
`verifier/renders/<page>.png` but there is **no equivalent for the reference**. The
task's `tests/reference_site/` ships only HTML/CSS — never PNGs — so the report's
`_reference_uri`, which reads `tests/reference_site/<screenshot>`, finds nothing.

We want the **actual reference pixels rendered at grade time** (sealed in-container
engine + bundled fonts — the exact images each score was computed against), not the
emit-time `environment/reference/` copies and not a host-font re-render.

## What to build

Persist the grade-time reference renders the same way EP-01 persists the candidate
renders, and repoint the report's reference loader at them.

### 1. Grader — persist the reference renders (mirror the candidate path)
`grade()` already opens each reference page into memory inside its scoring loop
(`reference_img = Image.open(reference_dir / spec["screenshot"])`). When called via
`--reference-site`, that `reference_dir` is the **sealed in-container render**, so
`grade()` already holds the exact pixels it scored — it just discards them.

- When `save_renders` is on, also write each `reference_img` to
  `<out_dir>/reference_renders/<page>.png`, keyed by **page name** (same keying as
  the candidate `renders/<page>.png`, NOT the `screenshot` filename — so the report
  loads them by page uniformly).
- Save the reference render **before** the candidate-missing `continue`, so a page
  whose candidate HTML is absent still gets its reference persisted (the report can
  show reference-vs-blank for a dropped page).
- Mirror the existing candidate block's structure (mkdir the dir once,
  `save_renders`-gated). Reuse the same in-memory image — no re-render.
- Keep this gated by the existing `save_renders` flag (default-on); `--no-save-renders`
  suppresses both candidate and reference renders.

### 2. Report — source the reference from the job, not the task
- Repoint `_reference_uri` from `task_path/tests/reference_site/<screenshot>` to the
  job's persisted `job_dir/task__<trial_id>/verifier/reference_renders/<page>.png`
  (keyed by page, exactly like `_render_uri` for the candidate). It now needs the
  **trial_id** — the reference render is deterministic and identical across trials,
  so use the trial_id of the candidate it is paired with (item 6: the best/worst
  render's trial for that page; item 7: the best-overall trial). Page-name keyed, so
  `page_map`'s `screenshot` field is no longer needed for the reference lookup.
- Update `_gallery_available` to gate on reference renders being present too (a job
  with candidate renders but — for a pre-EP-07 job — no `reference_renders/` should
  still degrade gracefully: candidate-only galleries, or omit the reference column,
  whichever is the smaller change; do NOT crash). Galleries still require candidate
  renders + page_map as today.
- The two gallery callers (`_per_metric_gallery_html`, `_best_overall_gallery_html`)
  pass the paired candidate's trial_id into `_reference_uri`.

### Storage layout (result)
```
jobs/<name>/task__<id>/verifier/
├── renders/<page>.png            ← candidate (EP-01, unchanged)
└── reference_renders/<page>.png  ← reference (this issue)
```
Per-trial, parallel to the candidate renders (identical across trials — acceptable
duplication; the per-trial sandboxes have no shared job-level dir).

## Acceptance criteria

- [x] With `save_renders` on, a grade run writes the sealed reference renders to
      `<out>/reference_renders/<page>.png` (one per page in the page_map), reusing
      the same in-memory images it scored — no re-render — and still writes
      `renders/<page>.png` for the candidate.
- [x] A page whose candidate HTML is absent still gets its reference render persisted.
- [x] `--no-save-renders` suppresses both candidate and reference renders.
- [x] The report's reference column in items 6 and 7 sources
      `verifier/reference_renders/<page>.png` (by page name), pairing each with the
      correct trial's candidate; the reference column is no longer blank.
      (Code + unit tests done; the faithful end-to-end reference column on a real
      job needs an HITL re-eval + report regeneration — the human will run that.)
- [x] A pre-EP-07 job (no `reference_renders/`) still produces a report without
      crashing (graceful degrade — galleries build from candidate renders, the
      reference column degrades to the `(no render)` placeholder).
- [x] Pure/unit-tested where it makes sense (the grader save behavior — on-disk shape;
      the report's URI/availability logic), matplotlib/HTML embedding stays untested
      shell. Full suite green (clean `TMPDIR`, Docker render test excluded): 317
      passed, 1 skipped.

## Blocked by

- None — can start immediately. Touches `grade/grader.py` (the save block) and
  `scripts/report.py` (`_reference_uri`, `_gallery_available`, the two gallery
  callers) + their tests. Independent of the reward-key change (EP-06) and the
  batch-eval orchestrator. After it lands, a re-eval of a task (e.g. 035) + report
  regeneration is needed to get faithful reference renders for that job (HITL, done
  by the human).
