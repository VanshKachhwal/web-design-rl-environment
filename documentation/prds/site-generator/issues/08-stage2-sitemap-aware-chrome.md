# 08 — Stage 2 sitemap-aware chrome (nav links resolve; no invented pages)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the first live single-site run.

## What to build

Stage 2 authors the header/nav/footer partials **blind to the sitemap**, so on a real
run it emitted web-style routes (`href="/features"`, `href="/"`) instead of the real
filenames, and invented pages that don't exist (`/login`, `/blog`, `/docs`, `/careers`…).
Result: clicking nav links navigates nowhere, and the links are broken internal refs.

Make stage 2 sitemap-aware:
- `build_stage2_prompt` must include the **page set with slugs** (`spec.page_map` / the
  ordered `spec.pages` titles + slugs).
- Instruct stage 2: nav/header/footer links must use the **exact relative filename**
  `<slug>.html` (home → `index.html`), and link **only** to pages in the sitemap —
  invent no pages.
- Add a gate **regression fixture** capturing what the live run produced (route-style
  `/features` links + hallucinated `/login` etc.) so the hermeticity broken-internal-link
  check provably catches it.

The gate's hermeticity check ("internal refs must resolve") is the safety net; this issue
makes stage 2 produce links that *pass* it (and actually navigate).

## Acceptance criteria

- [ ] The stage-2 prompt carries the sitemap (slugs + titles); a stub test asserts the
      page_map/slugs appear in the built prompt.
- [ ] Generated nav/header/footer link to `<slug>.html` (home → `index.html`), relative,
      and only to sitemap pages — no invented destinations.
- [ ] A hermeticity gate fixture covers route-style (`/features`) and hallucinated
      (`/login`) links and fails them as broken internal refs.
- [ ] Full suite green (clean `TMPDIR`).

## Blocked by

- None — can start immediately. (Highest priority with 13: together they gate a passing,
  navigable site.)
