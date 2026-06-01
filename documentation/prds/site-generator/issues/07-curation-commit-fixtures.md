# 07 — Curation shortlist → commit 10 fixtures

Status: ready-for-agent

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

Select the final ≥10 tasks from the gated survivor pool and commit them as reproducible
fixtures. This is the brief's "chosen to showcase the distribution and complexity" step — a
**coverage** selection, not "top-10 by score."

- **Greedy coverage shortlist** over the survivors' recorded seed tuples: distinct archetype
  + distinct aesthetic where possible, plus a complexity spread (~3 low / 4 medium / 3 high);
  dedupe falls out (two sites in one archetype×aesthetic cell can't both be picked).
- **Human confirmation pass** (HITL): a person eyeballs the shortlist of 10 and swaps any
  weak/samey ones — the research-taste pass.
- **Commit the 10** as fixtures (reference screenshots + emitted tasks), so the deliverable is
  reproducible even though LLM generation is non-deterministic.
- A short **coverage report** (which axis cells the 10 cover) so the distribution claim is
  auditable.

The quantitative coverage *metric* is deliberately deferred — see
`docs/design/task_selection.md`; this slice ships the greedy + human placeholder.

## Acceptance criteria

- [ ] The shortlist selects 10 from the survivor pool maximizing archetype + aesthetic
      distinctness with the target complexity spread, deduping same-cell candidates.
- [ ] A human confirmation step is supported (review + swap) before the set is finalized.
- [ ] The final 10 are committed as fixtures (screenshots + emitted Harbor tasks).
- [ ] A coverage report lists which taxonomy cells the 10 span.
- [ ] **Tests** (curation shortlist): given a synthetic survivor pool with known seed tuples,
      selection returns 10 with distinct archetypes/aesthetics and the target complexity
      spread, and dedupes same-cell candidates.

## Blocked by

- 06 (needs the gated survivor pool the batch produces).
