# 02 — `color` term (k-means palette + CIEDE2000)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

Add the `color` dimension to the grader as a new term that flows through the existing
aggregate → `reward.json` path. For each page pair, extract a dominant palette (~6 colors)
from both the candidate and reference screenshots via k-means with a **fixed random seed**
(determinism), match candidate→reference colors nearest-neighbor in Lab space, weight by
cluster frequency, average the CIEDE2000 ΔE, and normalize to [0,1] as `max(0, 1 − ΔE/100)`.
`color` joins `structure` as a second per-page term; the page score becomes the mean of the
available terms and `reward.json` gains a `color` key.

## Acceptance criteria

- [ ] `color` is a [0,1] float dimension added to `reward.json` and `reward-details.json`.
- [ ] Identical palettes score `color` ≈ 1.0; a hue-shifted variant scores lower; score decreases monotonically as palette ΔE grows.
- [ ] Deterministic across repeated runs (fixed clustering seed).
- [ ] Not gameable by matching mean color alone (a right-average / wrong-palette image scores low).
- [ ] Tests cover the `color` metric's external behavior.

## Blocked by

- Issue 01 (walking skeleton + aggregate contract).

## Comments

- **Done (2026-05-30).** Implemented via TDD, 19 passing tests (13 + 6 new). `color()` uses
  `scipy.cluster.vq.kmeans2` (seed=0, k≤6) for the palette + `skimage.color.deltaE_ciede2000`
  / `rgb2lab`; candidate→reference nearest-neighbor ΔE, candidate-frequency-weighted,
  normalized `max(0, 1−ΔE/100)`. No new deps.
- **Carry-forward fixed + future-proofed:** missing-page branch now zeros every dim via
  `{dim: 0.0 for dim in DIMENSIONS}` — new terms can't forget it.
- **Note for issue 06 (validation harness):** the mean-color anti-gaming case (mid-gray vs
  black/white reference) lands at `color ≈ 0.67`, not near-floor — a single gray sits ~ΔE 33
  from both extremes. The test asserts the *relative* drop (≥0.2 below a faithful candidate),
  which is the honest "reads palette, not mean" claim. Document a color-axis floor
  expectation in the monotonicity study.
- **For issues 03/04:** `reward.json`'s exact key set is asserted in
  `test_reward_json_has_expected_keys_and_ranges` — update it when each new dim lands.
