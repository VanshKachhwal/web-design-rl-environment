# 02 — Full taxonomy + stratified seeding + pure-helper tests

Status: done (committed 3a73c2e)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

Replace slice 01's minimal taxonomy with the full diversity engine, and make seed sampling
deterministic and coverage-spanning.

- **Taxonomy**: the stratified axes — `archetype` (~10), `aesthetic` (~10), `complexity`
  (3: low/med/high) — plus free modifiers (`audience/region`, `brand_mood`); per-archetype
  **page menus** (core ≥5 + optional, total ≤10, count coupled to complexity); and the
  **canonical ~20-type component catalog** (chrome / atoms / sections) that bounds the
  manifest's legal vocabulary.
- **Seeds**: a **stratified sampler** over the coverage grid → a deterministic ordered list
  of seed tuples (same count/order → same draw, no reproducibility-breaking RNG), and an
  expander turning a seed into a promptable spec.
- **Recorded seed tuple** per site `(archetype, aesthetic, complexity, audience, brand_mood)`
  for auditability and later curation.

The taxonomy and component catalog live in **one place** so generation, the manifest, the
gate, and curation all reference the same vocabulary.

## Acceptance criteria

- [ ] The coverage grid enumerates the expected archetype × aesthetic × complexity cells.
- [ ] Stratified sampling is **deterministic** (same count/order → identical seed list) and
      **spans** the grid (no single-cell clustering for a batch of ~48).
- [ ] Each archetype exposes a page menu whose page count lands in [5, 10] and tracks the
      complexity axis.
- [ ] The component catalog is the single legal vocabulary the manifest draws from.
- [ ] Each generated site records its seed tuple.
- [ ] **Tests** (pure helpers): grid enumeration; deterministic + spanning sampling; slug
      derivation (home→`index`, slugify, collision suffix, reserved stems) and `page_map`
      consistency (one token → `<slug>.html` + `<slug>.png` + key).

## Blocked by

- 01 (skeleton pipeline establishes the taxonomy/seed/slug seams this deepens).
