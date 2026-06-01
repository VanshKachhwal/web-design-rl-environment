# 18 — Relax token-compliance: enforce colors only on per-page styles (drop raw-px)

Status: done (committed 9f1a7bc)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live Modal batch: the
per-page token-compliance check nudged **every page, repeatedly**, all over a
`6px` literal —

```
gate: failed 26 check(s) ['token_compliance']
repair: nudging index (attempt 1/5): index.html: literal value 6px is not a token ...
repair: nudging schedule (attempt 1/5): schedule.html: literal value 6px is not a token ...
... (all 7 pages, then attempt 2/5 ...)
```

— burning ~16 LLM calls on a cosmetically-irrelevant literal and trending toward
dropping an otherwise-good site (and widening the window to hit a transient API
overload).

## Background / rationale

Token-compliance (issue 13) enforces that **per-page** styles (inline `style=""`
+ page `<style>`) use no hex/rgb/raw-px literal outside the declared
`variables.css` tokens; the frozen design system is exempt. Its purpose is
anti-drift — keeping the target's cross-page look coherent.

But the check protects the **generator's internal CSS hygiene**, which is
**invisible downstream**: the agent replicates from *screenshots* (never sees the
target CSS), and the grader scores *rendered-image* similarity (never inspects
whether the target used tokens). Splitting by what the rule catches:

- **Colors (hex/rgb)** — worth enforcing. An off-palette color on one page
  genuinely breaks visual/palette coherence and interacts with the color term.
- **Raw px (spacing / radii / borders)** — over-strict. A stray `6px` is a
  negligible coherence nit, invisible to agent + grader, and the model emits fine
  px values *naturally* (1px borders, 6px radii) that no coarse token scale fully
  covers. Enforcing it via LLM nudges is high-cost / low-value: each nudge is a
  full stage-3 regen, and a recurring literal can exhaust the nudge budget and
  **drop a good site** — lowering yield over nothing that matters downstream.

## What to build

Scope per-page token-compliance to **colors only**:

- **Stop flagging raw-`px` literals** in per-page styles (inline `style=""` +
  page `<style>` blocks). A page using `border-radius: 6px` / `gap: 6px` etc.
  must **pass**.
- **Keep flagging off-token colors** — a per-page `hex`/`rgb(...)` value that
  doesn't trace to a `variables.css` token still **fails** (repairable per-page),
  since color drift is real and downstream-relevant.
- **Keep the design-system exemption** (`variables.css` / `components.css`
  unchanged — still not literal-checked).
- Update the `token_compliance` description in the `quality_gate` module
  docstring + the `_check_token_compliance` docstring to the new color-only scope
  and the rationale (px invisible downstream; avoids nudge thrash / spurious
  drops).

Scope is **only** this relaxation — do not touch the other gate checks or the
repair loop.

## Acceptance criteria

- [x] A per-page inline/`<style>` raw `px` literal (e.g. `border-radius: 6px`)
      **passes** token-compliance (no diagnostic, no nudge).
- [x] A per-page off-token **color** (`#abc123` / `rgb(...)` not declared in
      `variables.css`) still **fails** token-compliance, keyed to the page.
- [x] A per-page color that exactly matches a declared `variables.css` token
      value still **passes**.
- [x] `variables.css` / `components.css` remain exempt (structural px + their own
      declarations don't trip the check).
- [x] The existing token-compliance test asserting a per-page `px` failure is
      updated to the new behavior; a per-page off-token-color failure test exists.
- [x] Module + function docstrings updated to the color-only scope. Full suite
      green (clean `TMPDIR`): 241 passed / 1 skipped (Docker render test excluded).

## Blocked by

- None. Narrows issue 13's check; touches only `quality_gate._check_token_compliance`
  and its CSS-value helpers.
