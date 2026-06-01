# 19 — Batch resilience: isolate per-seed failures (one seed can't sink the batch)

Status: done (committed 039f5c5)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live Modal batch: a single
seed hit an unretried API overload, its exception propagated out of the worker,
and because `worker.map(...)` raises on the first failed input, Modal **cancelled
every other in-flight container** — one transient blip wasted the entire run and
discarded the sibling seeds' partial work.

## Background

`run_one_seed` calls `generate_gated_site` (+ `build_task`) and returns a
`SeedResult`. A *gate* drop is already handled gracefully (returns
`status="dropped"`). But an **unexpected exception** (a transient API overload
past the retry budget, an OOM, a render crash, a Modal infra blip) propagates out
of `run_one_seed` → `_worker` → `worker.map`, which aborts the whole batch and
cancels the other seeds. For a 48-seed overgenerate run that means one bad seed
can cost all 48 (and the LLM spend already incurred on the cancelled ones).

A batch is an *overgenerate* step: individual seeds are expected to fail
sometimes. A seed failing should drop **that seed** and be recorded, never abort
the batch.

## What to build (pure-core, unit-testable — no Modal/network)

1. **Per-seed exception isolation in `run_one_seed`.** Wrap the pipeline so any
   unexpected exception is caught and returned as a new
   `SeedResult(status="errored", check=<exception class name>, reason=str(exc))`
   instead of propagating. A gate `Dropped` still returns `status="dropped"`
   (unchanged); only genuine exceptions become `"errored"`. The seed's own
   artifact dir is still written (partial work preserved); the worker still
   commits the volume.
2. **Report errored seeds.** Extend `summarize_batch` / `BatchReport` to count
   `errored` seeds distinctly from gate `dropped` ones (e.g. add `errored` and
   `errors_by_type`), and surface them in `format_report`. Yield stays
   passed / total.
3. **Don't let the fan-out abort on a stray failure.** With (1) the worker no
   longer raises for application errors, so `worker.map` won't abort on those. If
   the installed Modal version supports it, also pass `return_exceptions=True` (or
   the equivalent) when consuming the map so an *infra*-level failure (OOM /
   timeout / container crash) surfaces as a per-input error the loop records
   rather than aborting the batch — verify against the installed Modal API; if
   unsupported, document it and rely on (1).

Scope is **only** failure isolation + reporting — do not change generation, the
gate, or the retry logic (the transient-overload retry is a separate issue).

## Acceptance criteria

- [x] A seed whose pipeline raises (stub a client that raises mid-run) yields a
      `SeedResult(status="errored", check=..., reason=...)` from `run_one_seed` —
      no exception propagates.
- [x] A gate `Dropped` still yields `status="dropped"` (unchanged); a pass still
      yields `status="passed"`.
- [x] `summarize_batch` counts `passed` / `dropped` / `errored` distinctly;
      `BatchReport` exposes the errored count (+ `errors_by_type`); `format_report`
      shows it. Yield = passed / total.
- [x] An errored seed leaves other seeds' artifacts untouched (per-seed dir
      isolation already holds — confirmed by a sibling-survives test).
- [x] The installed Modal (1.4.3) supports `return_exceptions` on `.map`; the
      consumption loop uses it and records infra-level failures as errored
      `SeedResult`s instead of aborting the batch.
- [x] Pure core unit-tested with stubs (no Modal); module stays import-safe
      without `modal`; full suite green (clean `TMPDIR`, Docker render test
      excluded): 246 passed / 1 skipped.

## Blocked by

- None. Builds on issue 06's `modal_batch` (`run_one_seed`, `SeedResult`,
  `summarize_batch`). Independent of — and complementary to — the streaming-
  overload retry fix (point 1; a separate issue): that *reduces* failures, this
  *survives* them.
