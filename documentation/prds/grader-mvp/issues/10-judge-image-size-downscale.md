# 10 — Judge image-size: downscale before the VLM call (and fail loud, never fake a reward)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`. Fixes a live grading failure hitting batch evals.

## Problem

The LLM judge (`grade/judge.py`) sends full-page screenshots to the Anthropic
vision API with **no resizing** (`_encode_png` base64s the image at full
resolution, whatever the scroll height). The API **hard-rejects any image whose
dimension exceeds 8000px** with a 400 `invalid_request_error`
(`...image dimensions exceed max allowed size: 8000 pixels`). This is a universal
API limit across all Claude models — NOT a Sonnet weakness.

Our screenshots are 1280px wide × variable height; content-dense pages blow past
8000px tall. Real data from the current batch: **5 of 12 jobs crashed**
(`001/009/010/013/014`, 0/10 trials graded); the tallest render is **1280×11706**,
and because it's a *deterministic* `reference.png`, that task fails the judge on
**every** trial.

Worse, there is **no error handling** in the judge path: a single oversized page's
400 propagates out of `grade()` *before* `reward.json` is written, so the **entire
multi-page trial is lost** — all four terms, every page — and the trial errors with
no reward.

## What to build

Two parts. The first removes the cause; the second keeps reward integrity when the
judge fails for any *other* reason.

### 1. Downscale images before the judge call (the real fix)

In `grade/judge.py` `_encode_png` (the single choke point both reference and
candidate pass through), downscale so **neither dimension exceeds 8000px** before
encoding:
- Resize a **copy** (LANCZOS), preserving aspect ratio; **only** when the long edge
  exceeds the cap; **never upscale**. A module constant (e.g. `_MAX_EDGE = 8000`).
- It must be **non-mutating**: the persisted full-res renders (`renders/` and
  `reference_renders/`, EP-01/EP-07) are written by `grade()` from the original PIL
  images and must stay **full resolution** — only the judge-bound encoded copy is
  downscaled. (The API downscales to ~1568 long edge internally anyway, so capping
  at 8000 is behavior-preserving for the judge's view while eliminating the 400.)

### 2. No silent degrade — fail loud on any *other* judge failure

`design_judge` is an **integral quarter of the reward**. With the size error fixed,
any *remaining* judge failure is genuinely unexpected and must stay **visible** — we
must NOT silently emit a 3-term reward that hides a missing integral term (a
complete-looking-but-incomplete reward is worse than a missing one you can re-run).
- Do **not** add a swallow-and-degrade path. Wrap the per-page judge/scoring call
  (in `grade()`'s page loop, where the page name is in scope) **only** to log a
  clear, page-tagged error (`judge/scoring failed on page <page>: <err>`) and
  **re-raise** — so the trial errors loudly (as it does today) and the operator
  knows which page and why.
- Explicit non-goal: this issue does **not** add multi-page crash-resilience. A
  genuine judge error still errors the whole trial — deliberate (reward **integrity**
  over resilience), because the integral judge term must never be silently absent.
- Catch scope is therefore **narrow**: log-and-re-raise for diagnostics only; nothing
  is swallowed into a degraded reward.

## Acceptance criteria

- [x] `_encode_png` downscales the encoded image so **both** dimensions are ≤ 8000px
      (resize a copy, LANCZOS, aspect-preserving, only when exceeded, never upscale).
      A `1280×11706` image encodes within the limit; a small image is unchanged.
- [x] The downscale is **non-mutating**: `grade()` still writes **full-resolution**
      `renders/<page>.png` and `reference_renders/<page>.png` (unchanged by this
      issue) — only the bytes sent to the judge are downscaled.
- [x] `design_judge` remains a full four-term contributor for normal pages (the
      downscale does not change term count or the deterministic terms).
- [x] A judge failure for a reason **other** than image size is **not** swallowed:
      it is logged with the page name and **re-raised** (the trial errors); no
      `reward.json` is written with a silently-dropped judge term. Covered by a unit
      test with a stub `judge_client` that raises — assert the error propagates
      (and, if a logging seam is available, that the page is logged), and that the
      grade does NOT produce a degraded 3-term reward.
- [x] Unit tests are pure (no live API): the downscale logic asserted on PIL image
      dimensions in→out; the fail-loud behavior with a raising stub client. No
      network / real Anthropic call.
- [x] Full suite green (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None. Touches `grade/judge.py` (`_encode_png` + the downscale constant) and
  `grade/grader.py` (the page-tagged log-and-re-raise in the loop) + their tests.
  Independent of the in-flight CLI work. After it lands, the paused batch can resume:
  delete the crashed job dirs (`001/009/010/013/014` — no `result.json` survivors
  re-run) and re-launch `evaluate-all` (the launcher refreshes the baked grader to
  this fix).
