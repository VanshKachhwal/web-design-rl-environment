# 25 — generate CLI: a thin command to kick off a Modal batch generation

Status: done

## Parent

PRD: `.scratch/site-generator/PRD.md`. Promotes the `scripts/generate.py` stub into a
real CLI over `modal_batch.run_batch`, mirroring the `scripts/evaluate.py` /
`scripts/report.py` thin-shell pattern. Sibling: issue 26 (`pull_artifacts`).
Grill-resolved this session.

## What to build

A CLI that kicks off a batch generation on Modal — the command form of today's
`python -m webdesign_rl.generate.modal_batch` (which runs `run_batch()` with all
defaults). It exposes `--count`, `--concurrency`, and `--volume`, threading the
latter two through `run_batch` into `_build_modal_app` (both are hardcoded constants
today). `run_batch` already prints the `BatchReport`.

**1. Make `concurrency` + `volume` parameters (small `modal_batch` change).**
- `_build_modal_app()` currently reads the module constants `DEFAULT_CONCURRENCY`
  (used as `max_containers`) and `VOLUME_NAME` (used in
  `modal.Volume.from_name(...)`). Give it parameters with those constants as
  defaults: `_build_modal_app(*, concurrency=DEFAULT_CONCURRENCY,
  volume_name=VOLUME_NAME)`, and use them in `max_containers=` and the
  `Volume.from_name(...)` call. `SECRET_NAME` / `VOLUME_MOUNT` stay constant.
- `run_batch(count=DEFAULT_BATCH_SIZE)` gains keyword params:
  `run_batch(count=DEFAULT_BATCH_SIZE, *, concurrency=DEFAULT_CONCURRENCY,
  volume=VOLUME_NAME)`, passed straight into `_build_modal_app(...)`. Existing
  call sites (`__main__`, any test) keep working via the defaults.
- Keep the import-safety contract: no module-level Modal usage; the app is still
  lazily built inside `run_batch`.

**2. Thin shell (`scripts/generate.py`) — untested.**
- argparse CLI: `--count N` (default `DEFAULT_BATCH_SIZE`, 48), `--concurrency N`
  (default `DEFAULT_CONCURRENCY`, 10), `--volume NAME` (default `VOLUME_NAME`,
  `webdesign-rl-artifacts`).
- Calls `run_batch(count=…, concurrency=…, volume=…)`. `run_batch` prints the
  `BatchReport`; the CLI does not add its own report file (print-only).
- This is the live-cloud HITL shell (mirrors `modal_batch.__main__`): mark it
  `# pragma: no cover`. It must stay **import-safe** without `modal` installed
  (don't import modal at module top; `run_batch` already defers Modal).

**Auth assumption (unchanged):** generation relies on **Modal token auth**
(`modal token new`) **+ the `anthropic-api-key` Secret** — NOT `.env`. Flexible
credential sourcing (env-file path / OS env) is tracked separately in
`docs/improvements.md` and is out of scope here.

## Acceptance criteria

- [x] `_build_modal_app` accepts `concurrency` + `volume_name` params (defaulting to
      the existing constants) and uses them for `max_containers` and
      `Volume.from_name`; `SECRET_NAME`/`VOLUME_MOUNT` unchanged.
- [x] `run_batch` accepts `concurrency` + `volume` keyword params (defaulting to the
      constants) and threads them into `_build_modal_app`; existing zero-arg/`count`
      call sites still work.
- [x] `scripts/generate.py` exposes `--count` / `--concurrency` / `--volume` and
      invokes `run_batch` with them; `run_batch` prints the `BatchReport`.
- [x] Module + script are import-safe without `modal` (no top-level modal import);
      `generate.py --help` renders. (Verified structurally: importing both modules
      leaves `modal` out of `sys.modules`, and `--help` renders. Modal *is*
      installed in this venv at 1.4.3, so the literal "uninstall modal" check is
      proven by the no-top-level-import structure rather than a missing dep.)
- [x] Unit test (pure, no Modal/network) that the new params are **plumbed** —
      `monkeypatch.setattr(modal_batch, "_build_modal_app", fake)` where `fake(*,
      concurrency, volume_name)` records the kwargs and returns a stub
      `(app, worker)` whose `app.run()` is a no-op CM and `worker.map()` is an empty
      stream, so `run_batch` short-circuits to an empty `BatchReport` without
      touching Modal. Asserts `run_batch(count=N, concurrency=C, volume=V)` passed
      `C`/`V` through, plus a defaults-plumb-the-constants test. The live-cloud path
      (`app.run()`, the actual fan-out) stays untested shell.
- [x] Full suite green (clean `TMPDIR`, Docker render test excluded). The batch
      wrapper stays import-safe without `modal`. (327 passed / 1 skipped.)

Not verifiable without a live Modal run: the actual cloud fan-out — that
`max_containers=concurrency` and `Volume.from_name(volume)` take effect against
real Modal — is the untested HITL shell by design.

## Blocked by

- None. Touches `generate/modal_batch.py` (`run_batch` + `_build_modal_app` params)
  and `scripts/generate.py` (the stub). Independent of issue 26 (`pull_artifacts`) —
  they share only the volume-name convention, not code.
