# 10 — Configurable stage-3 repair budget (2 → 5)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Requested after the first live run — losing a whole
site to one stubborn page after generating everything is wasteful.

## What to build

Raise the per-page stage-3 nudge budget from 2 to **5**, and make it a **named parameter**
of `generate_gated_site` (default 5) rather than a magic number, so it's tunable without a
code edit.

## Acceptance criteria

- [ ] The per-page nudge budget is a parameter of `generate_gated_site` (default 5).
- [ ] A fixable-after-N-nudges page (N in 3..5) is now repaired rather than dropped.
- [ ] Budget exhaustion still drops the site with a logged reason (unchanged behavior at
      the limit).
- [ ] Tests assert the new default and the exhaustion path; full suite green.

## Blocked by

- None — can start immediately.
