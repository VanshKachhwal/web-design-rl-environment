# 06 — Modal batch runner: overgenerate ~48 → gate → emit survivors

Status: done (committed 924cb40)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

Scale the per-site pipeline to a batch on Modal. The per-site pipeline is embarrassingly
parallel across seeds and must run **in the sealed image** that also renders and grades — so
reference screenshots are produced in the exact environment they're graded in.

- **`.map()` fan-out** of `generate_site` over the stratified seed list (~48) in the sealed
  image.
- **Artifacts to a volume** keyed by seed id (idempotent: a dropped site doesn't lose the
  others; re-runs are addressable).
- **Concurrency cap / backoff** so the fan-out doesn't trip Anthropic rate limits.
- **Emit each survivor** as a Harbor task via the existing packaging.
- **Measured yield + per-check telemetry** reported (gate pass-rate over the batch, AND
  per-check diagnostic frequency) — the operationalized "stable recipe" number, plus the
  data to tune the gate (e.g. whether to relax token-compliance's raw-`px` rule) with
  evidence instead of by guess.

## Build & test approach (TDD; stubbed now, live run is HITL)

Split into a **testable pure core** + a **thin Modal wrapper** (lazy-import `modal`, keep the
module import-safe and unit-tested with no Modal/Anthropic calls — same pattern as
`AnthropicGenerationClient`):

- **Pure core (unit-tested with `StubGenerationClient` + an injected render):** seed-list
  construction with a deterministic `seed_id`; a per-seed worker that runs
  `generate_gated_site`, writes artifacts under `<volume>/<seed_id>/`, emits the task on
  pass, and returns a structured `SeedResult`; idempotent re-run keyed by `seed_id`; a
  `summarize_batch(results)` that computes yield + per-check telemetry.
- **Thin Modal wrapper (not unit-tested):** `app` / sealed `image` (reuse the render image)
  / `Volume` / a `.map()` fan-out with a concurrency cap, and a `modal.Secret` for
  `ANTHROPIC_API_KEY`. The live cloud run is a HITL step the human drives.

Telemetry needs two small, non-invasive changes to `llm_site_generator`: enrich `Dropped`
with the fatal `check` name (new field, defaulted — backward compatible), and let
`generate_gated_site` populate an optional `stats` collector (default `None` → no behavior
change) with per-check nudge counts / gate rounds, so `summarize_batch` can attribute both
drops and nudge-churn to a check.

## Acceptance criteria

- [x] A batch run fans out ~48 seeds on Modal, each running the full gated pipeline in the
      sealed image. *(Thin wrapper `_build_modal_app` + `run_batch`: concurrency-capped
      `.map()` over `enumerate(sample_seeds(48))`; worker renders with the direct in-image
      `render_site`. Untested shell over the tested core; live cloud run is HITL.)*
- [x] Survivor task artifacts land in a volume keyed by seed id; a mid-batch failure doesn't
      lose other sites; a re-run is addressable/idempotent per seed id. *(`run_one_seed`
      writes `<out_root>/<seed_id>/{site,task}`; clears only that seed's dir on re-run —
      `test_rerun_is_addressable_and_preserves_other_seeds`.)*
- [x] Concurrency is capped so the batch completes without rate-limit failures.
      *(`@app.function(max_containers=DEFAULT_CONCURRENCY=8)`; client retries/backs off.)*
- [x] Each survivor is emitted as a runnable Harbor task. *(`run_one_seed` calls
      `build_task` on pass — `test_run_one_seed_passing_writes_site_and_task`.)*
- [x] The run reports measured gate yield **and per-check diagnostic frequency**
      (drop-cause-by-check at minimum; nudge-by-check if cheap). *(`summarize_batch` ->
      `BatchReport.{yield_fraction,drops_by_check,nudges_by_check}`; `format_report` logs it.)*
- [x] The pure core (seed ids, per-seed worker, idempotency, `summarize_batch`) is unit-tested
      with stubs and no live calls; the Modal wrapper is import-safe (lazy `modal`). Full
      suite green (clean `TMPDIR`). *(`tests/test_generate_modal_batch.py`, 14 tests;
      237 passed / 1 skipped excluding the Docker render test.)*

## Blocked by

- 02 (full taxonomy/stratified seeds for a real spanning batch)
- 04 (the full gated + emit single-site pipeline this fans out)
- 05 (the palette image the batch renders in)
