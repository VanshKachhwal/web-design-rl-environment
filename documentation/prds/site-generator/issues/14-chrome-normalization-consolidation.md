# 14 — Stage-3 body normalization + chrome consolidation (one header, one footer)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live single-site run: pages
rendered with **2 headers, 2 footers, and 3 navs**, and the site was dropped on
`chrome must be byte-identical across pages`.

## Background (what the live run showed)

`index.html` contained three navs from two independent bugs:
- **Bug A — stage-3 in-body chrome.** Stage 3 is told to return only `<main>…</main>` but
  the model added a full `<header><nav>…</nav></header>` and `<footer>` *inside* `<main>`,
  with placeholder `#` links — inconsistently across pages. The orchestrator injects the
  real chrome on top → duplicate + per-page-inconsistent chrome → chrome-identity gate fails
  (unrepairable by per-page nudges, which keep re-adding it).
- **Bug B — partial redundancy.** The orchestrator injects `header_html` **and** a separate
  `nav_html`, but stage 2 already puts the `<nav>` *inside* the `<header>` — so there are
  two (correct, duplicate) navs even with zero stage-3 problems.

The genuine page-to-page links live in the stage-2 header and are already correct
(`index.html`/`features.html`/…) — issue 08 worked. So the fix is about **eliminating the
duplicates deterministically**, not about the links.

## What to build (goal: simple, clear, robust — chrome enforced in code, not by the model)

**Part 1 — Stage-3 body normalization (deterministic).** Before assembly, normalize the
stage-3 output to section content only:
- **strip every `<header>`, `<nav>`, and `<footer>` element (at any nesting depth)** from the
  stage-3 markup — use an HTML parser (stdlib `html.parser`, as `quality_gate` already does;
  do NOT use brittle regex for nested tags);
- keep the remaining section content and ensure it is wrapped in exactly one `<main>…</main>`
  (if stage 3 already returned a `<main>`, use its content; otherwise wrap what's left).

This makes duplicate / inconsistent chrome **impossible by construction** — chrome comes
only from the injected partials. Also tighten the stage-3 prompt ("return ONLY the
`<main>…</main>` element with section content — no `<header>`, `<nav>`, `<footer>`, or
page wrapper") so stripping rarely has to do work.

**Part 2 — Consolidate chrome to header + footer (simplify the model).** A standard page is
`<header><nav>…</nav></header> … <footer>…</footer>`. So:
- the **header partial owns the nav** (stage 2 authors the sitemap-aware `<nav>` inside the
  header, as it already does);
- **drop the separate nav partial entirely** — `DesignSystem` chrome becomes
  `header_html` + `footer_html` (plus `variables_css` + `components_css`); the stage-2
  delimited format drops the `nav.html` block (4 blocks, not 5); the stage-2 prompt asks for
  header (with nav) + footer; the assembly injects **header + body + footer** only.

Update every stage-2 stub in the tests to the 4-block format.

## Acceptance criteria

- [ ] Every generated page has **exactly one `<header>` (containing one `<nav>`) and one
      `<footer>`**, and **zero** header/nav/footer inside `<main>`.
- [ ] Stage-3 normalization strips nested header/nav/footer and yields a single `<main>`;
      unit-tested against markup that wrongly includes in-body chrome (the live failure).
- [ ] `DesignSystem` no longer carries a separate nav partial; stage-2 format is 4 blocks;
      assembly injects header + footer only; stage-2 prompt + all stubs updated.
- [ ] The chrome-identity gate passes (header/footer byte-identical across pages); the nav
      links are the stage-2 `<slug>.html` links (verified resolvable).
- [ ] Full suite green (clean `TMPDIR`); zero regressions.

## Blocked by

- None (builds on the uncommitted 08–13 work already in the tree).
