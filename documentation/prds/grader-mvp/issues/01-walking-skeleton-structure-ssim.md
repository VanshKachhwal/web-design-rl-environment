# 01 — Walking skeleton + `structure` (SSIM) end-to-end

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

The grader's walking skeleton: a standalone function that takes a candidate directory, a
reference directory, and a `page_map`, and produces the scored output — proving the full
spine of metric → aggregate → output before any other term or live rendering exists.

For this first slice the inputs are **pre-rendered screenshot fixtures** (hand-made PNGs);
live HTML rendering arrives in a later slice. For each page in the `page_map`, load the
candidate and reference screenshots, resize the candidate to the reference's dimensions, and
compute a single deterministic term — **grayscale single-scale SSIM** (`structure`). Average
the per-page `structure` score into the task scalar `reward`, and write `reward.json` (flat:
`reward` + the `structure` dimension) plus `reward-details.json` (per-page breakdown). A
required page missing from the candidate scores 0 and drags the mean.

`page_map` maps a logical page to its reference screenshot and required candidate filename,
e.g. conceptually `{ "home": { "screenshot": "home.png", "expected_file": "home.html" } }`.

Include a small hand-made reference page + a couple of candidate variants as committed test
fixtures.

## Acceptance criteria

- [ ] `grade(candidate_dir, reference_dir, page_map)` runs standalone and writes `reward.json` + `reward-details.json`.
- [ ] `reward.json` is a flat object with `reward` and `structure` floats in [0,1].
- [ ] Candidate is resized to reference dimensions before SSIM; SSIM computed on grayscale.
- [ ] Identical candidate vs reference scores `structure` ≈ 1.0; a clearly different image scores meaningfully lower; SSIM decreases monotonically under increasing blur/shift.
- [ ] Multi-page reward is the mean of per-page scores; a missing required page contributes 0.
- [ ] Tests cover SSIM behavior and the aggregation math (external behavior only).

## Blocked by

None - can start immediately.

## Comments

- **Done (2026-05-30).** Implemented via TDD, 13 passing tests. Built `grade/metrics.py`
  (`structure` SSIM), `grade/aggregate.py` (dimension-agnostic), `grade/grader.py`
  orchestrator, committed PIL fixtures under `tests/fixtures/`.
- **Contract tweak:** `grade()` gained an `out_dir` arg →
  `grade(candidate_dir, reference_dir, page_map, out_dir)` so writes are deterministic
  (Harbor packaging passes `/logs/verifier`). Reflected in `docs/design/grader_design.md`.
- **Carry-forward:** the missing-page branch in `grader.py` hardcodes `"structure": 0.0`
  in the details dict — later terms must zero **all** dims there.
