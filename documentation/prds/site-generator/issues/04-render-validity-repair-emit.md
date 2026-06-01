# 04 — Stage-5 render validity + bounded repair + emit one gated task

Status: done (committed 55eb053)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

Complete the gate and the per-site orchestrator, then close the loop by emitting one fully
gated site as a runnable Harbor task — the first full local end-to-end.

- **Stage-5 render validity** (reusing the render module): each page renders clean at 1280px,
  **deterministically** (render twice → identical), is **not blank**, and has **no
  catastrophic layout** (no horizontal overflow, zero-height sections, clipped/overlapping
  elements, off-screen content).
- **Orchestrator** (`generate_site`): fail-fast **inline gates** after stage 1 (sitemap ≥5,
  manifest well-formed) and stage 2 (manifest compliance) with **≤2 re-rolls** each then skip
  the seed; full gate (stage 4 + 5); **stage-3 nudge loop** — re-invoke the failing page with
  the exact diagnostic, **≤2 nudges/page**, composition-only against frozen artifacts, then
  **drop the site**; every drop **logged with its reason**.
- **Emit**: hand a gated site to the **existing emit packaging** → a runnable Harbor task.

## Acceptance criteria

- [ ] Stage-5 passes a good site and fails/diagnoses blank, non-deterministic, and
      catastrophic-layout fixtures.
- [ ] Inline gates re-roll ≤2× then skip the seed; the stage-3 nudge loop repairs a fixable
      page (≤2 nudges) and drops an unfixable site, logging the reason.
- [ ] Repair is composition-only: a page fix never rewrites `variables.css`/`components.css`.
- [ ] A gated site is emitted via the existing packaging and `harbor run oracle` (Docker)
      yields reward ≈ 1.0.
- [ ] Existing tests stay green.

## Blocked by

- 03 (the repair loop consumes stage-4 diagnostics; stage 5 extends the same gate module).
