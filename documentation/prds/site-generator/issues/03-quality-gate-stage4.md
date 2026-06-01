# 03 — Quality gate: stage-4 deterministic checks + fixture tests

Status: done (committed b2e0c41)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

The deterministic half of the quality gate: a `quality_gate` module whose stage-4 checks
verify a generated site is a valid, well-posed target, returning **precise, repair-ready
diagnostics** (which check failed, on which page/file, with what message). Interface:
`(site_dir, spec) → GateResult{passed, diagnostics[]}`.

Stage-4 checks (all deterministic, ~free):

- **Completeness** — all sitemap pages generated; HTML/CSS parse; shared files exist and
  link-resolve.
- **Target identity** — canonical page set + fixed filenames + `page_map` present; every
  reference page maps 1:1 to an expected agent filename.
- **Per-page substance** — ≥3 distinct catalog components (excl. header/footer) **AND**
  ≥50 words real text **AND** rendered height ∈ [600px, 12000px].
- **Token compliance** — no hex/rgb/px value not traceable to a declared `var(--…)`.
- **Manifest compliance** — every section a page references resolves to a styled stage-2
  component.
- **Chrome identity** — header/footer/nav byte-identical across pages.
- **Hermeticity** — no external resource loads (fonts/images/CSS/JS) → fail; internal refs
  must resolve; external `<a>` hyperlinks allowed but inert.
- **Static-only** — fail on `<script>`, `@keyframes`/`animation:`, and interaction-*reveal*
  rules (`:hover/:focus/:target/:checked` toggling `display`/`visibility`/`opacity`/
  `max-height` of content); allow `transition` + cosmetic hover; disclosure components must
  render open.

(Stage-5 render validity + repair live in slice 04.)

## Acceptance criteria

- [ ] `quality_gate` returns a structured `GateResult` with per-check, per-page diagnostics
      precise enough to drive a repair nudge.
- [ ] A well-formed fixture site passes all stage-4 checks.
- [ ] **Tests** (against good/bad fixture sites), each check firing in isolation: off-token
      value flagged; referenced-but-unstyled component flagged; external font/image/CSS/JS
      flagged while inert external `<a>` passes; near-empty page fails the substance floor
      while a rich page passes; `<script>`/`@keyframes`/interaction-reveal fail while
      `transition`/cosmetic-hover pass; missing/mismatched page fails target-identity.

## Blocked by

- 01 (skeleton pipeline produces the sites and `spec` shape the gate consumes).
