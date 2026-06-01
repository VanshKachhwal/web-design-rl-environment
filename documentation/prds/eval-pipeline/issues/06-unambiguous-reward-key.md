# EP-06 — Make `reward` the unambiguous canonical metric in reward.json

Status: done

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md` (the
"make the reward key unambiguous" follow-up flagged there and in memory
`eval-pipeline-status`). Disjoint from the deferred batch-eval orchestrator
(tracked in `docs/improvements.md`).

## Problem

The grader writes a **flat five-key** `reward.json`:

```json
{ "structure": 0.75, "color": 0.97, "content": 0.61, "design_judge": 0.74, "reward": 0.77 }
```

`reward` is the canonical aggregate (equal-weight page-mean of the four terms), but
nothing marks it as canonical — it's one of five sibling floats. Harbor treats
**every** key as a metric, re-serializes them alphabetically when aggregating the
job (`metrics[0]` = `color, content, design_judge, reward, structure`), and
`harbor view`'s job-list headline features the **first** key → **`color` (~0.97)**.

Consequences:
- **Top-down view is misleading.** Color is the model's strongest, lowest-variance
  term, so every task's headline reads ~0.97 and the real signal (reward ~0.757,
  content the bottleneck ~0.55) is hidden one level down. Scanning `harbor view
  jobs/` makes all tasks look uniformly excellent.
- **Latent RL hazard.** A training/reward-kit consumer that grabs "the metric" from
  a five-key `reward.json` has no unambiguous signal of which key is the reward to
  optimize — it could optimize `color` instead of `reward`.

This is a *display/convention* defect, not a numeric bug: `reward` is computed
correctly and present; it's just not the surfaced/canonical one.

## What to build

Slim the emitted `reward.json` to the **single scalar aggregate** so Harbor (and any
reward-kit consumer) sees exactly one, unambiguous metric:

```json
{ "reward": 0.7574745441283558 }
```

Keep the full four-term breakdown where it already lives — `reward-details.json`
already embeds the complete five-key dict under its top-level `"reward"` key
(verified on both a fresh grade and the existing `jobs/opus47-004/` job), plus the
per-page terms and judge sub-scores. **No information is lost**; the per-term
breakdown moves from "a peer key Harbor mis-features" to "the details file + our
report, which already feature `reward` and break out all four terms."

Then repoint the report harvester's per-term reads from `reward.json` to
`reward-details.json["reward"]`. Because `reward-details.json` has always carried
the full dict, this works **uniformly for old and new jobs with no back-compat
branching** — `jobs/opus47-004/` (old five-key `reward.json`) still harvests
identically.

**Forward-compatibility of the 50 generated tasks:** the curated/survivor task
packages store the *grader code* (baked `tests/webdesign_rl_pkg`), not rewards. The
eval launcher's `prepare_eval_copy` refreshes that baked package to current repo
code on every eval copy, so this grader change auto-applies the next time any task
is evaluated. **No regeneration or re-curation of `out/passed-batch-50/` is needed.**
Already-written historical job artifacts (e.g. `jobs/opus47-004/` reward.json) stay
in the old format and are not rewritten — the harvester reads them fine anyway.

### Scope of edits
- **Grader** (`grade/grader.py` + the `aggregate`/`grade` docstrings, and
  `grade/aggregate.py`'s "flat payload" description): `reward.json` gets only
  `{"reward": <float>}`. `reward-details.json` is **unchanged** (still
  `{"reward": <full five-key dict>, "pages": {...}}`). `grade()`'s return value
  (the in-process flat dict consumed by callers/tests) should stay the full dict —
  only the **on-disk `reward.json`** is slimmed.
- **Harvester** (`eval/aggregate_results.py`): read the trial aggregate from
  `reward.json["reward"]` (still valid) and the four terms from
  `reward-details.json["reward"]` instead of from `reward.json`. Per-page terms are
  already read from `reward-details.json["pages"]` — unchanged.
- **Verify nothing else parses the four flat terms out of `reward.json`** (the only
  reader is the harvester; the verifier `test.sh` just writes it; `grade/__main__`
  and `aggregate.py` are writers/describers).

## Acceptance criteria

- [x] Emitted/written `reward.json` contains exactly one key, `reward`, a float.
- [x] `reward-details.json` is unchanged — still carries the full five-key term dict
      under `"reward"` plus per-page terms and judge sub-scores.
- [x] `grade()`'s in-process return value still exposes the full four-term + reward
      dict (callers/tests that read terms from the return value keep working).
- [x] The harvester produces an **identical** normalized scores object as before
      (same trial-level four terms + reward, same per-page terms) by reading terms
      from `reward-details.json`; verified against a fixture job and against the
      existing `jobs/opus47-004/` (old-format `reward.json`) — no back-compat branch.
- [x] A grade run (deterministic-only is fine) asserts the slim `reward.json` shape
      and the unchanged `reward-details.json` shape on disk.
- [ ] `harbor view jobs/` job-list headline shows `reward` for a newly-run job
      (manual/HITL confirmation note; not an automated test). — NOT verified here
      (requires running Harbor; left for HITL).
- [x] No regeneration of `out/passed-batch-50/`; full suite green (clean `TMPDIR`,
      Docker render test excluded): 313 passed, 1 skipped.

## Blocked by

- None — can start immediately. Touches `grade/` (writer) + `eval/aggregate_results`
  (reader) and their tests; independent of the batch-eval orchestrator.
