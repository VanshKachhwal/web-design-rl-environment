# 17 — Stage-3 body links constrained to the sitemap (no invented routes)

Status: done (committed cd040bc)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live single-site run
(event-conference / retro-y2k / med): the `hermeticity` check produced 5 real
diagnostics for **invented internal links in page bodies**:

```
index.html:  internal link href=/get-started does not resolve to a bundled file
index.html:  internal link href=/demo        does not resolve to a bundled file
venue.html:  internal link href=/register     does not resolve to a bundled file
```

## Background

Issue 08 made the **stage-2 chrome** nav sitemap-aware (header/footer links point
at real `<slug>.html` files). But **stage-3 page bodies** are composed without the
sitemap, so CTA buttons ("Get Started", "Register", "View Demo") link to
made-up routes (`/get-started`, `/demo`, `/register`) that are not real pages.
The gate's hermeticity check is **correct** to fail these — a broken internal link
in the target site is a well-posedness defect. (This finding was masked in the
live run only because the site-wide `font_palette` failure (issue 16) fired first
and dropped the site before the per-page link failures could be repaired.)

`build_stage3_prompt` currently passes only the page's sections + the frozen
design system — never the sitemap. `_sitemap_lines(spec)` already exists (stage 2
uses it). The stage-3 body is already deterministically normalized by
`normalize_stage3_body` / `_BodyNormalizer` (issue 14 strips nested chrome) — the
natural place to *also* enforce link resolvability in code.

## What to build (mirror issue 08 for body content; enforce in code like issue 14)

**Part 1 — sitemap-aware stage-3 prompt.** Pass the sitemap into
`build_stage3_prompt` (reuse `_sitemap_lines`). Instruct: every link in the body
must point at one of the exact sitemap `<slug>.html` filenames, or be inert
(`#`, `mailto:`, `tel:`); never invent a route (`/get-started`, `/demo`,
`/register`) and never use web-style absolute paths (`/`, `/features`). This lets
the model route a CTA to the *right* real page intelligently.

**Part 2 — deterministic link normalization (safety net).** Extend the stage-3
body normalization so a broken body link is impossible by construction: rewrite
any `<a href>` that is **internal and unresolvable** to `#`. Mirror the gate's
`_resolves` rule exactly — preserve `#fragment`, `mailto:`, `tel:`, and external
`http(s)://` links (inert/allowed); for everything else, strip query/fragment and
keep it only if its filename is one of the sitemap `<slug>.html` pages, otherwise
rewrite the href to `#`. `run_stage3` passes the set of valid page filenames
(derived from `spec.page_map` / `spec.pages`) into the normalizer. Use the stdlib
HTML parser path already in `_BodyNormalizer` (not brittle regex) so it composes
with the existing chrome-strip.

## Acceptance criteria

- [x] `build_stage3_prompt` includes the sitemap and the body-link rule (link only
      to a real `<slug>.html` or be inert; no invented/absolute routes).
- [x] Stage-3 body normalization rewrites an internal unresolvable `<a href>` to
      `#` — unit-tested against the live failure (`href="/get-started"` → `#`,
      `href="/register"` → `#`).
- [x] External `http(s)://` links, `#fragment`, `mailto:`, and `tel:` hrefs are
      preserved unchanged; real page links (`tickets.html`, `tickets.html#x`) are
      preserved.
- [x] `run_stage3` threads the valid page-filename set into the normalizer; the
      chrome-strip behavior from issue 14 is unchanged.
- [x] A stage-3 body with invented-route CTAs no longer yields any hermeticity
      "internal link does not resolve" diagnostic after normalization.
- [x] Full suite green (clean `TMPDIR`); existing stage-3 / normalizer tests still
      pass (update them for the new `normalize_stage3_body` signature).

## Blocked by

- None. Mirrors issue 08 (sitemap-aware chrome) for body content and builds on
  issue 14's `_BodyNormalizer`.
