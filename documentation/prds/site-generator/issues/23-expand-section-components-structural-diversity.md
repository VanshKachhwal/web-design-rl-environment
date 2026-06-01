# 23 — Expand the section-component catalog for structural diversity + usage telemetry

Status: done (committed 6b37e71)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Addresses the open **diversity review**
finding (see `docs/design/generator_design.md` / memory): archetype/aesthetic/
content diversity is already good, but **(a) layout grammar repeats** (every site
hero→features→testimonial→cta→footer) and **(b) the component catalog is
SaaS-biased** (non-SaaS archetypes repurpose ill-fitting components — e.g. a
restaurant Menu using `pricing-table`). This issue attacks *those* axes by
widening the canonical component catalog and measuring whether it helps.

## What to build

Widen `SECTION_COMPONENTS` with two families, add a minimal static-only signal so
the new components stay well-posed, and add per-component **usage telemetry** to
the batch report so the next batch *proves* whether structural diversity improved.

**Keep the change small and non-breaking.** The catalog is consumed by code that
already generalizes over it: stage-1's manifest is "drawn from the canonical
component catalog", and the gate's `manifest_compliance` checks membership against
`taxonomy.legal_components()`. So **adding to the tuple auto-flows everywhere** —
the catalog widening itself is a tuple edit, no gate/stage changes. Do not refactor
surrounding code.

### 1. New section components (append to `SECTION_COMPONENTS`)

**Layout-pattern components** (drive structural variety, all static/CSS-drawable):
`bento-grid`, `timeline`, `comparison-table`, `sidebar-layout`, `masonry-grid`,
`split-screen`, `step-process`.

**Archetype-specific components** (fix the SaaS-bias — archetype-native sections):
`menu-card`, `speaker-card`, `job-listing`, `metric-dashboard`, `code-snippet`,
`filter-bar`, `newsletter-signup`, `map-embed-placeholder`, `award-badge`.

Fixes applied to the proposed list:
- `job-listing` (not the typo `job-ing`).
- **Dropped `sticky-nav-section`** — sticky/scroll behavior is invisible in a
  single full-page 1280px screenshot, so it adds no gradable diversity over
  `sidebar-layout`. Keep `sidebar-layout`, omit the sticky variant.
- `map-embed-placeholder` is explicitly a **static, CSS-drawn placeholder** (no
  `<iframe>`, no JS, no external tiles) — else the static-only + hermeticity gates
  drop it.
- `metric-dashboard` / `code-snippet` are **CSS/SVG-drawable only** (no charting
  libraries, no JS) — crude bars / monospace blocks are fine.

### 2. Minimal static-only signal

Add a **single, minimal** note to the relevant stage prompt that the new
components are **static / CSS-drawable placeholders** (so `map-embed-placeholder`,
`metric-dashboard`, `code-snippet` don't tempt an iframe / charting lib / JS). Keep
it to one clause; do **not** rewrite the prompt. If a prompt-content test would
break, update that assertion minimally rather than reshaping the prompt.

### 3. Per-component usage telemetry (minimal, reuse the existing pattern)

Surface which components actually get used across a batch, so we can verify (not
assume) the grammar diversified and spot any component that drives drops. Reuse the
**existing `stats` → `SeedResult` → `summarize_batch`** threading that
`nudges_by_check` already uses:
- thread the stage-1 `component_manifest` (the declared section union, already on
  the Spec) into the `stats` dict the gated pipeline populates;
- carry it onto `SeedResult` as a new field **with a default** (so every existing
  construction site / test keeps working);
- aggregate a `components_used` tally (count of seeds using each component) in
  `summarize_batch` / `BatchReport` (a new field **with a default**) and show it in
  `format_report`.

No new module; mirror `nudges_by_check` exactly.

## Acceptance criteria

- [ ] `SECTION_COMPONENTS` includes the new layout-pattern + archetype-specific
      components above (with `job-listing`, without `sticky-nav-section`);
      `COMPONENT_CATALOG` / `legal_components()` include them automatically.
- [ ] No gate change needed: `manifest_compliance` already accepts any catalog
      member (a site whose manifest uses a new component, with a matching
      `components.css` rule, passes that check) — verified by a unit test.
- [ ] A minimal static-only prompt signal names the new components as
      static/CSS-drawable; any affected prompt-content test updated minimally.
- [ ] `BatchReport` gains a `components_used` tally (new field with a default);
      `summarize_batch` aggregates it from `SeedResult`; `format_report` shows it;
      `run_one_seed` populates the per-seed component list from the pipeline `stats`.
- [ ] All new dataclass fields have defaults so existing `SeedResult` /
      `BatchReport` construction and tests don't break.
- [ ] Any test asserting the exact component-catalog contents/size is updated.
- [ ] Pure, deterministic unit tests (no live API / Modal / network); the batch
      wrapper stays import-safe without `modal`. Full suite green (clean `TMPDIR`,
      Docker render test excluded).

## Blocked by

- None. Touches `generate/taxonomy.py` (+ a one-line stage-prompt note in
  `generate/stages.py`), and `generate/modal_batch.py` (+ `llm_site_generator.py`
  for the stats thread) for telemetry — plus their tests. Disjoint from the
  in-flight eval-pipeline work (`eval/` + `scripts/`).
