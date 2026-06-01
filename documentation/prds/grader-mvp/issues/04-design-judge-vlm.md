# 04 — `design_judge` term (VLM rubric, stubbable)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

Add the `design_judge` dimension: one call to a vision LLM (Sonnet-class, deliberately
**different** from the Opus 4.7 agent under test, temperature 0) given both the REFERENCE and
CANDIDATE screenshots clearly labeled. The judge returns a small numeric rubric
(layout/alignment, color/palette, typography, content-completeness, each 0–10 with brief
anchors); the module averages the rubric into one [0,1] `design_judge` score. Sub-scores are
recorded in `reward-details.json`.

The model call must sit behind a thin client interface so the deterministic logic
(prompt assembly, rubric parsing, averaging, edge-case handling) is testable **without live
API calls**. With all four terms present, the per-page score is the equal-weight mean
(0.25 each) and `reward.json` carries all four dimensions plus `reward`.

## Acceptance criteria

- [ ] `design_judge` is a [0,1] float dimension; rubric sub-scores appear in `reward-details.json`.
- [ ] Judge uses a model distinct from the agent under test, at temperature 0, one sample.
- [ ] The VLM client is injectable/stubbable; no live API calls occur in the test suite.
- [ ] Tests assert only that a **stubbed** rubric response parses into the correct averaged score and that malformed/edge responses are handled gracefully.
- [ ] Final per-page reward = mean of the four equally-weighted terms.

## Blocked by

- Issue 01 (walking skeleton + aggregate contract).

## Comments

- **Done (2026-05-30).** Built in a parallel worktree (alongside issue 03), merged to main.
  `judge.py` defines a `JudgeClient` Protocol (`score(reference_img, candidate_img) -> {field:
  0-10}`), `judge_rubric()`/`design_judge()` averaging four sub-scores (layout_alignment,
  color_palette, typography, content_completeness) → [0,1], an `AnthropicJudgeClient`
  (claude-sonnet-4-6, temp 0, lazy import — import-safe with no key), and a `StubJudgeClient`
  for tests. **No live API calls in the suite.**
- **Signature change (merged):** `grade(candidate_dir, reference_dir, page_map, out_dir,
  judge_client)` — the judge client is injected. Sub-scores logged to `reward-details.json`.
- `anthropic` was already a declared dependency; no pyproject change needed.
