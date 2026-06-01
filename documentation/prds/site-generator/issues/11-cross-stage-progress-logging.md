# 11 — Cross-stage progress logging

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Requested after the first live run — the pipeline
runs for minutes with no feedback.

## What to build

Emit INFO-level progress logging through the gated pipeline so a live run shows where it
is, using the standard `logging` module (the orchestrator already logs drops via
`logger.warning`):

- stage 1 — generating brief + sitemap (then: N pages, the slugs)
- stage 2 — authoring design system (then: components count)
- stage 3 — `page i/N: <title>` as each page is generated
- gate — running stage 4 / stage 5; pass or the failing checks
- repair — `nudging <slug> (attempt k/budget): <diagnostic>`
- inline re-rolls (stage 1/2) and drops (already logged) at a consistent level

## Acceptance criteria

- [ ] A run (stub or live) emits ordered, readable progress lines for each stage, each
      page, the gate, and any repair/re-roll/drop.
- [ ] Uses the `logging` module (no bare prints in library code); no secrets/API keys
      logged.
- [ ] A test asserts the key progress events are logged (e.g. via `caplog`).
- [ ] Full suite green.

## Blocked by

- None — can start immediately.
