# 16 — Font-palette check resolves var() tokens + effective-font semantics

Status: done (committed 91b28f2)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live single-site run
(event-conference / retro-y2k / med), which was **dropped on 51 `font_palette`
diagnostics** that are all false positives.

## Background (what the live run showed)

The model authored `variables.css` with proper font tokens — every value a real
palette stack:

```
--font-body: "Work Sans", "Inter", "Archivo", Verdana, "Trebuchet MS", sans-serif;
--font-heading: "Anton", "Space Grotesk", Trebuchet MS, sans-serif;
--font-display: "Playfair Display", "Anton", Georgia, serif;
--font-mono: "JetBrains Mono", "Courier New", Courier, monospace;
--font-ui: "Space Grotesk", "Inter", Verdana, sans-serif;
```

…and referenced them in `components.css` via `font-family: var(--font-body)`. The
gate's `_font_families()` extracts the literal comma-tokens of each `font-family`
declaration, so it reads the *string* `var(--font-body)` and fails it — it is
**blind to `var()` indirection**. Result: 51 false `font_palette` failures, on the
shared `components.css`, so it is classified site-wide and the site is dropped
unrepairably.

This is also the source of the recipe's flakiness: earlier runs (saas/swiss,
restaurant) happened to *inline* literal family names (`font-family: Inter,
sans-serif`) and passed; this run defined tokens and referenced them — the
*better* practice — and the same gate failed it. Same check, nondeterministic
pass/fail depending on which style the model picks.

A second, secondary inflation: even after resolving `var()`, the model's stacks
carry non-palette web-safe fallbacks (`Verdana`, `Georgia`, `Trebuchet MS`,
`Courier New`). A strict per-family rule would still fail those — but they are
**inert**: none are installed in the sealed render image, so the browser skips
them to the palette family that actually renders.

## What to build (in `quality_gate._check_font_palette` + helpers)

1. **Resolve `var()` tokens.** Parse `variables.css` for `--name: value` custom
   properties into a token map. When a `font-family` value references
   `var(--x[, <fallback>])`, resolve `--x` from the map (recursively, with a
   visited-set so a token cycle terminates) and validate the resolved stack;
   validate the inline `<fallback>` portion too. An `undeclared` `var(--x)` (no
   matching token) is a **real** failure with a distinct, clear message (not the
   generic "not in palette" one).
2. **Effective-font semantics — validate each stack as a whole, not per family.**
   A `font-family` stack **passes iff** it contains **≥1 palette family**
   (`fonts.PALETTE_FAMILIES` + the `DejaVu Sans` fallback) **OR** consists only of
   generic keywords (`fonts.GENERIC_FAMILIES`). Non-palette *concrete* families
   alongside a palette family are tolerated as inert fallbacks. A stack whose only
   concrete family is off-palette and which has no palette family (e.g.
   `"Comic Sans MS", sans-serif`) still **fails** — that is the off-palette
   *primary* the check exists to catch.
3. **Parsing care.** Split a `font-family` value into its stack on **top-level
   commas only** — do not split inside `var(...)` (its fallback list contains
   commas). A value may be a bare `var(--x)`, a full stack `var(--x), serif`, or a
   literal stack.
4. Keep per-file / per-page keying so a per-page failure still routes to the
   stage-3 nudge loop. The design-system stylesheets and per-page styles are all
   scanned (as today).

## Acceptance criteria

- [x] `components.css` using `font-family: var(--font-body)`, where `--font-body`
      resolves (from `variables.css`) to a stack containing a palette family,
      **passes** the font-palette check.
- [x] A `var(--x)` with no matching declaration in `variables.css` **fails** with a
      clear "undeclared token" message (distinct from the off-palette message).
- [x] A stack with a palette family **plus** non-palette web-safe fallbacks
      (`Verdana`, `Georgia`) **passes**.
- [x] A stack with an off-palette primary and **no** palette family
      (`"Comic Sans MS", sans-serif`) still **fails**.
- [x] A pure-generic stack (`sans-serif`) **passes**.
- [x] Recursive `var()` (a token referencing another token) resolves; a cyclic
      definition terminates without infinite loop.
- [x] The previously-dropped live site (`out/run_med`) now clears `font_palette`
      (verified by hand: 51 → 0; not a committed test).
- [x] Existing `font_palette` tests are updated to the new semantics; full suite
      green (clean `TMPDIR`): 216 passed, 1 skipped.

## Blocked by

- None. Builds on issue 05's `fonts` manifest (`PALETTE_FAMILIES`,
  `GENERIC_FAMILIES`, `FALLBACK_FAMILY`) and issue 13's design-system scoping
  pattern.
