# EP-10 — report-all: build a report for every job in a jobs dir

Status: done

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: grill-resolved this session (the batch
eval orchestrator parked in `docs/improvements.md`). Sibling slice: EP-09
(`evaluate-all`). Builds on `report.py` / `eval/aggregate_results.py` (EP-03/04) and
the persisted renders (EP-01/07).

## What to build

A checkpoint that runs the existing per-task report (`report.py`'s `build_report`:
harvest → `scores.json`/`scores.csv` + self-contained `report.html` with items 1–7)
over **every job in a given jobs directory** — the same thing `report.py` does for
one job, but swept across a directory of jobs. Decoupled from eval (reports are
fast/cheap vs the eval+grade pipeline, so this is its own command and can be re-run
freely).

It does **not** re-implement reporting — it drives the existing
`build_report(job_dir, out_dir)` once per discovered job. New code = job discovery +
a loop + per-job failure isolation.

**Pure core (report side — no matplotlib/HTML needed to test):**
- **Job discovery** — a pure function taking a jobs directory and returning the job
  dirs inside it, **sorted/deterministic**. A job dir is a subdir that carries a
  `result.json` (the harvester's entry point); subdirs without one (stray files,
  non-job dirs) are skipped. This is the unit-tested seam (drive it on a temp tree
  with a mix of real job dirs + noise).
- Output-path derivation: each job → `reports/model-eval/<job-dir-name>/` (the same
  `_default_out` convention `report.py` uses).

**Thin shell (`scripts/report_all.py`) — untested:**
- argparse CLI: positional `jobs_dir` (e.g. `jobs/` — your responsibility to point
  it at a dir holding the jobs you want), `--out-root` (default
  `reports/model-eval`).
- For each discovered job dir, call `build_report(job_dir, out_root/<name>)`.
  **Serial** (reports are fast) and **always-regenerate** (no skip — you want fresh
  reports after re-evals).
- **Failure isolation:** a single job that fails to harvest/report (e.g. a malformed
  job dir) is caught and logged; the sweep continues. Print an `ok/failed` tally at
  the end. (Pre-EP-07 jobs without `reference_renders/` are NOT failures — they
  degrade gracefully per EP-07/08.)
- No cross-task aggregate / index.html / summary.csv — **deferred** (per-task
  reports only).

## Acceptance criteria

- [x] `report-all <jobs_dir>` builds a `report.html` (+ `scores.json`/`scores.csv`)
      for every job dir found under `<jobs_dir>` (a subdir with `result.json`),
      writing each to `reports/model-eval/<job-dir-name>/`. (Smoke-run against the
      real `jobs/opus47-035` produced report.html + scores.json/csv; default
      out-root is `reports/model-eval`.)
- [x] Non-job subdirs (no `result.json`) are skipped; discovery is deterministic.
- [x] Serial, always-regenerate (no skip logic); re-running rebuilds all reports.
- [x] One job's report failure does not abort the sweep; an `ok/failed` tally prints
      at the end. Pre-EP-07 jobs (no `reference_renders/`) still report (graceful
      degrade via `build_report`), not counted as failures.
- [x] No cross-task aggregate emitted (deferred).
- [x] **Pure core unit-tested**: job discovery on a synthetic tree (job dirs with
      `result.json` + a `task__abc/result.json` trial subdir + noise dir/loose file)
      returns exactly the job dirs, sorted, never recursing into trial dirs. The
      `build_report` loop + matplotlib/HTML is the untested shell — same split as
      `report.py` itself.
- [x] Module import-safe; full suite green (clean `TMPDIR`, Docker render test
      excluded): 325 passed, 1 skipped.

## Blocked by

- None — `build_report` (EP-03/04) already exists and works on any single job dir;
  this slice is independently usable **today** against your existing `jobs/`
  (no EP-09 required). Independent of EP-09 — they share only the `jobs/` convention.
