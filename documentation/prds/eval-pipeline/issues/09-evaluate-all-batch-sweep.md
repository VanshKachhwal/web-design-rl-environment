# EP-09 — evaluate-all: parallel eval sweep over a whole curated batch

Status: done

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: grill-resolved this session (the batch
eval orchestrator parked in `docs/improvements.md`). Sibling slice: EP-10
(`report-all`). Builds on `evaluate.py` / `eval/run_claude_code.py` (EP-02) and
`generate/curate.py` (issue 24).

## What to build

A checkpoint that runs the existing per-task eval (`evaluate.py`'s path: clone →
refresh package → flip agent internet → `harbor run` Opus-4.7 ×10) over **every
survivor task in a curated/output dir**, a few in parallel, unattended-friendly.

It does **not** re-implement the eval — it drives the existing
`run_claude_code.launch(...)` once per task. New code = discovery + a parallel
scheduling loop + per-task failure isolation.

**Pure core (new, in the `eval/` module — no network, no Harbor):**
- **Survivor discovery** — reuse `curate.survivors(batch_dir)` to get the
  fully-emitted tasks (`Survivor(seed_id, archetype, aesthetic, complexity, path)`;
  the task dir is `survivor.path / "task"`). Sorted/deterministic (already is).
- **Batch plan** — a pure function turning `(batch_dir, jobs_dir, prefix, force,
  limit)` into an ordered list of per-task plans: `{seed_id, task_path, job_name,
  skip}` where:
  - `job_name` = the **bare survivor seed_id** by default (e.g.
    `035_local-service_dark-techy_high`); an optional `--prefix` namespaces it.
  - `skip` = `not force and (jobs_dir/job_name/result.json).exists()` — i.e.
    **skip-completed** (a finished job has a `result.json`; a half-written/crashed
    job dir without one is NOT skipped, so it re-runs).
  - `--limit N` caps the number of **to-run** (non-skipped) tasks.
  This plan is the unit-tested seam (deterministic; no I/O beyond the existence
  check, which is easy to drive on a temp tree).

**Thin shell (`scripts/evaluate_all.py`) — untested:**
- argparse CLI: `--batch <curated dir>`, `--parallel N` (default 2),
  `--concurrency N` (per-task `-n`, default 10), `--prefix`, `--limit N`, `--force`,
  plus the pass-throughs `--model` / `--executor` / `--yes` that `evaluate.py` has.
- Builds the plan; runs the **to-run** tasks through a thread pool of size
  `--parallel`, each calling `run_claude_code.launch(task_path=…, name=job_name,
  concurrency=…, …)` (which subprocess-invokes `harbor`). So `--parallel 2` ×
  `--concurrency 10` = up to **20 concurrent** agent sessions on the one shared key
  (above the validated baseline of 10 — `--parallel 1` backs it off).
- **Failure isolation:** catch a per-task launch failure (mirror
  `modal_batch.run_one_seed`'s try/except), log it, keep going. At the end print an
  `ok / failed` **tally** with the failed seed_ids. Skip-completed means a re-run
  retries only the failures.
- No cost estimate / confirmation prompt — it just runs.

## Acceptance criteria

- [x] `evaluate-all --batch <dir>` discovers all survivor tasks (via
      `curate.survivors`) and launches the existing per-task eval for each.
      (Discovery in `build_plan`; the launch loop in `scripts/evaluate_all.py` —
      live launch path is the untested shell, needs a live run to exercise.)
- [x] `--parallel N` runs N evals concurrently (thread pool of subprocess launches);
      each task uses `--concurrency` for its own `-n`. Default `--parallel 2`,
      `--concurrency 10`. (ThreadPoolExecutor(max_workers=--parallel) in the shell;
      live concurrency needs a live run.)
- [x] Job names default to the bare survivor seed_id; `--prefix` namespaces them.
- [x] Skip-completed: a task whose `jobs/<job_name>/result.json` exists is skipped;
      `--force` re-runs it. A job dir lacking `result.json` is NOT skipped.
- [x] `--limit N` caps the number of to-run tasks.
- [x] One task's failure does not abort the batch; an `ok/failed` tally (with failed
      seed_ids) prints at the end. (try/except per task + tally in the shell; the
      live failure path needs a live run.)
- [x] **Pure core unit-tested** on a synthetic batch tree (survivor dirs + drop-only
      dirs + a pre-existing completed job + a half-written job): the plan picks the
      right tasks, derives names, applies skip/force/limit, in deterministic order.
      No network / Harbor / Modal. The thread-pool + `harbor` subprocess path is the
      untested shell.
- [x] Module import-safe without `harbor`/`modal`; full suite green (clean `TMPDIR`,
      Docker render test excluded). 325 passed / 1 skipped.

## Blocked by

- None — `evaluate.py` / `run_claude_code.launch` (EP-02) and `curate.survivors`
  (issue 24) already exist. Independent of EP-10 (report-all) — they share only the
  `jobs/` directory convention, not code.
