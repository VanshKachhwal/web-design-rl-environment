# 01 — End-to-end skeleton: one site generated → rendered locally

Status: done (committed 576a367)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

The thinnest end-to-end path through the whole generation pipeline: a single function
`generate_site(seed) → site_dir` that runs all three stages and produces a renderable,
multi-page (**≥5 pages**) static HTML/CSS site. This is the build-order "generate one site
locally and eyeball it" step — it establishes every seam later slices deepen.

Breadth is intentionally minimal here (a handful of archetypes/aesthetics is fine; full
taxonomy is slice 02). What matters is that the stages **connect** and the output **renders**:

- **Stage 1** (seed → spec): brief + sitemap (with slugs → `page_map`) + per-page section
  list + component manifest.
- **Stage 2** (spec → frozen design system): `variables.css` (tokens) + `components.css`
  (the manifest's components) + header/footer/nav partials, authored as real CSS in **one
  call**.
- **Stage 3** (per page, fanned out): compose the frozen artifacts into each page's HTML,
  referencing only declared tokens/classes; inject the chrome partials byte-identically.

All LLM calls go through a **thin, stubbable client** (same pattern as the grader's judge),
using Opus 4.6 at temps 1.0 / 0.7 / 0.6. The produced site is rendered locally to per-page
screenshots by **reusing the existing render module** (no new rendering code).

## Acceptance criteria

- [ ] `generate_site(seed)` produces a site directory with ≥5 pages, `variables.css`,
      `components.css`, header/footer/nav partials, and one HTML file per sitemap page.
- [ ] Slugs derive deterministically from the sitemap (home → `index`); `page_map` maps each
      slug → `{screenshot, expected_file}` in the shape the existing emit/grader consume.
- [ ] Every page references only the frozen `variables.css`/`components.css` + injected
      partials; header/footer/nav are byte-identical across pages.
- [ ] The site renders cleanly via the existing render module at 1280px to one full-page
      screenshot per page.
- [ ] LLM access is behind a stubbable client interface; a stubbed run produces a site with
      no live API call.
- [ ] A documented local command generates one site and renders it for visual review.

## Blocked by

- None — can start immediately.
