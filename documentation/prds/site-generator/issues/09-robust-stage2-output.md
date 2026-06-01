# 09 — Robust stage-2 output (eliminate truncation / escaping fragility)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the first live single-site run
(stage 2 truncated mid-`components_css` → unterminated-JSON crash).

## What to build

Stage 2 currently returns `variables.css` + the whole `components.css` + 3 HTML partials
embedded in **one JSON object**, which is fragile two ways: (a) the response can truncate
mid-string at `max_tokens`, and (b) large multi-line CSS inside a JSON string is
escaping-prone. A bigger `max_tokens` is a ceiling, not a fix. Do all three:

1. **Bump `max_tokens`** to a model-verified-safe high value (confirm `claude-opus-4-6`'s
   output cap; don't hardcode a value the API will reject).
2. **Detect truncation** — read the Messages API `stop_reason`; if it's `max_tokens`,
   raise a clear, actionable error (or retry with a continuation) instead of letting the
   parser crash on an unterminated string.
3. **Switch stage 2 to an escape-free, token-efficient delimited format** (e.g.
   `===FILE variables.css===\n…\n===FILE components.css===\n…`) parsed by splitting on
   markers — no JSON escaping of multi-line CSS, and detectable if a marker is missing.

Note: stage-2 output is **bounded by the component manifest** (a subset of the ~20-type
catalog), independent of page count — so high complexity does not enlarge stage 2, and one
call with a generous cap + efficient format suffices at all complexity levels.

> **Superseded by issue 15 (continuation-on-truncation).** A live run falsified the "one
> call suffices at all complexity levels" premise: the manifest itself grows with page count
> and verbose aesthetics inflate per-component CSS, so stage 2 *can* exceed even a 32000 cap.
> The robust fix is no longer "a generous cap" but the client transparently **continuing** a
> `max_tokens` response via assistant-prefill (issue 15). The escape-free `===FILE===` format
> and missing-block detection above still hold.

## Acceptance criteria

- [ ] Stage 2 parses reliably for a large (near-full-catalog) design system.
- [ ] A truncated/`stop_reason == max_tokens` response yields a clear error (or handled
      continuation), never a cryptic JSON crash.
- [ ] The delimited stage-2 format round-trips (parse tests); stage-2 stub tests updated.
- [ ] `max_tokens` set to a value the model actually accepts (verified, not assumed).
- [ ] Full suite green (clean `TMPDIR`).

## Blocked by

- None — can start immediately.
