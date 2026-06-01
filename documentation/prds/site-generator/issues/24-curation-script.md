# 24 — Curation script: survivor filter + coverage shortlist (AFK core of 07)

Status: done (committed 49cb576)

## Parent

PRD: `.scratch/site-generator/PRD.md`. This is the **AFK, testable core** of issue
07 (curation → commit fixtures); 07 keeps the HITL tail (human eyeball + committing
the final fixtures). Selection logic spec: `docs/design/task_selection.md`.

## What to build

A reusable **curation** step that turns a downloaded generation batch into a
survivor pool and a coverage-maximizing shortlist — replacing the ad-hoc copy-paste
snippet run after every batch. Split into a pure, unit-tested core + a thin I/O
shell, mirroring `modal_batch` (pure `summarize_batch` + thin Modal wrapper) and
`aggregate_results` (pure harvest + thin report shell).

Modules: pure core in `src/webdesign_rl/generate/curate.py`; thin CLI in
`scripts/curate.py` (new).

**Pure core (`generate/curate.py`) — no network, no Modal:**
- **`survivors(batch_dir)`** — the seed dirs that are *fully-emitted tasks* (a
  `task/task.toml` present; gate drops / errors leave a `site/` but no task). Return
  each survivor's id + parsed seed tuple. The dir name is
  `{index:03d}_{archetype}_{aesthetic}_{complexity}` (from `modal_batch.seed_id`), so
  splitting on `_` with maxsplit 3 yields `[index, archetype, aesthetic, complexity]`
  cleanly (archetype/aesthetic use `-`, never `_`). Cross-checking the survivor's
  recorded `seed.json` is optional but fine.
- **`dedupe_by_cell(survivors)`** — at most one survivor per `(archetype, aesthetic)`
  cell (lowest index wins). Deterministic. (Post-issue-21 this is usually a no-op,
  but keep it — it's the dedupe guarantee.)
- **`select_coverage(pool, n=10, complexity_spread=(3,4,3))`** — a greedy
  coverage shortlist: maximize **distinct archetypes**, then **distinct aesthetics**,
  while hitting the target complexity spread (~3 low / 4 med / 3 high for n=10);
  same-cell candidates can't both be picked (dedupe falls out). Best-effort when the
  pool can't satisfy the exact spread (don't crash — fill to `n` by best remaining
  coverage and report the shortfall). Deterministic for a given pool.
- **`coverage_report(selected)`** — a structured summary of which taxonomy cells the
  shortlist covers vs misses (archetypes hit/missed, aesthetics hit/missed, the
  realized complexity spread) + a `format_*` string (reuse the
  `modal_batch._fmt_counts` idiom or similar), so the distribution claim is auditable.

**Thin shell (`scripts/curate.py`) — untested:**
- argparse CLI: `--batch <dir>` (e.g. `out/batch-50-run1`), `--out <dir>` (e.g.
  `out/curated-50`), `--select N` (optional; default = keep all survivors / dedup
  only), `--spread l,m,h` (optional). It runs the pure core, **copies** the chosen
  survivor dirs into `--out`, and prints the coverage report. The filesystem copy +
  print are the untested shell.

**Out of scope here (stays in 07):** committing the final fixtures into the repo, and
the human review/swap pass. This script *produces the shortlist + coverage report*;
a human then eyeballs and commits.

## Acceptance criteria

- [ ] `survivors(batch_dir)` returns only fully-emitted survivors (task/task.toml
      present), each with its parsed seed tuple; sites without a task are excluded.
- [ ] `dedupe_by_cell` keeps at most one survivor per `(archetype, aesthetic)` cell
      (lowest index), deterministically.
- [ ] `select_coverage(pool, n=10)` returns ≤ n survivors maximizing distinct
      archetypes/aesthetics with the target complexity spread, deduping same-cell
      candidates; best-effort (no crash) when the pool can't meet the exact spread,
      and the shortfall is visible in the coverage report.
- [ ] `coverage_report` lists which taxonomy cells the shortlist covers/misses + the
      realized complexity spread.
- [ ] `scripts/curate.py` filters a batch dir → copies the chosen survivors into the
      out dir → prints the coverage report.
- [ ] Pure-core unit tests on a **synthetic survivor pool** with known seed tuples
      (mix of survivors + drop-only dirs + same-cell duplicates): survivor filter
      excludes the drop-only dirs; dedupe collapses same-cell; select returns the
      target count with distinct archetypes/aesthetics + the target spread; coverage
      report names the covered/missed cells. No network/Modal/live generation.
- [ ] Module import-safe; full suite green (clean `TMPDIR`, Docker render test
      excluded).

## Blocked by

- None to build (06 is done; the survivor pool exists). 07's *commit/eyeball* tail
  depends on this producing the shortlist.
