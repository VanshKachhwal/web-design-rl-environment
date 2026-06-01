# 09 — Font-consistent agent screenshots (bundle DejaVu via @font-face)

Status: wontfix (superseded — see Comments)

## Parent

PRD: `.scratch/grader-mvp/PRD.md` (split out of issue 08)

## Scope note

Split out of the original issue 08. Issue 08 makes `emit` render the reference
screenshots and place them in the agent environment, but renders them on the
**host** (macOS → Arial/Helvetica). This issue makes that render **font-consistent
with grading**.

## What to build

Grading renders the reference *in-container* (DejaVu fonts). Issue 08 renders the
agent-facing screenshots on the host (macOS → Arial/Helvetica). Different glyph
metrics → different line wrapping → the agent replicates a layout it is then graded
against in DejaVu → systematic ~10% structure penalty (this is exactly the issue-07
0.91 bug). Fix by **bundling a font via `@font-face`** so host and container render
with identical metrics.

## Acceptance criteria

- [ ] A font (DejaVu Sans — copy the `.ttf` from matplotlib's bundled fonts, no
  download) is bundled into the reference sites and referenced via `@font-face`;
  the fixture sites use it as their text font.
- [ ] The committed reference render PNGs (`tests/fixtures/site5_render_reference/`)
  are regenerated with the bundled font.
- [ ] The bundled font ships in the verifier `reference_site/` too, so the
  in-container reference render and the host-rendered agent screenshots (issue 08)
  use the same font (matching layout).
- [ ] **Regression:** `harbor run -a oracle` still yields reward ≈ 1.0 (Docker up).
- [ ] Existing tests stay green.

## Notes

- DejaVu Sans `.ttf` is available locally at the matplotlib data dir
  (`.venv/.../matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf`) — copy it, don't
  download.
- `@font-face` keeps *layout* consistent host-vs-container; subpixel antialiasing
  differences are negligible for SSIM.
- This is the first slice of the curated-font-bundle described in
  `docs/design/generator_design.md`; a full multi-font palette + generation
  constraint is still later generation work.

## Blocked by

- Issue 08 (places the agent screenshots this issue makes font-consistent).

## Comments

**2026-05-31 — Superseded by site-generator issue 05; do not build the `@font-face` patch.**

This issue's plan (bundle DejaVu via `@font-face` so host-rendered agent screenshots match
the in-container grading render) was a minimal MVP patch for the *single fallback font on a
macOS host*. The generator design supersedes it with a more fundamental fix:

- Fonts are installed **OS-level** (curated palette vendored as `.ttf` into the
  render/verifier image, referenced by **bare family name**) — mandatory anyway so the
  agent's `font-family: Inter` resolves in the verifier render.
- The agent's reference screenshots are rendered **in-container** (the same sealed image as
  grading), so there is no host vs container font environment to reconcile — the root cause
  of the issue-07/09 bug disappears rather than being patched.

That work is tracked in `.scratch/site-generator/issues/05-font-palette-incontainer-screenshots.md`
(blocked by site-generator issue 01). The oracle ≈ 1.0 regression this issue cared about is
an acceptance criterion there. See `docs/design/generator_design.md` (V1 decisions, font row)
for the rationale.
