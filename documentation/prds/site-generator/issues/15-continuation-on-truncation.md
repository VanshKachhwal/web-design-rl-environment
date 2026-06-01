# 15 — Continuation-on-truncation (handle responses that exceed the output cap)

Status: done (committed 6639bac)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Completes the deferred "(or retry with a
continuation)" option left open in issue 09 (`09-robust-stage2-output.md`).

## Background (what the live run showed)

Issue 09 switched stage 2 to the escape-free `===FILE name===` format and made a
`stop_reason == "max_tokens"` response raise a clear error. It also asserted that "stage-2
output is **bounded by the component manifest** … independent of page count — so high
complexity does not enlarge stage 2, and one call with a generous cap suffices at all
complexity levels." **A live run falsified that premise.**

The `event-conference / retro-y2k / med` seed (7 pages) crashed stage 2 at
`max_tokens=16384`:

```
ValueError: generation response was truncated at max_tokens (16384); the model hit the
output cap before finishing. Raise max_tokens or shrink the requested output.
```

Two compounding causes: (a) the manifest *itself* grows with page count — more pages
produce a wider union of section types, so `components.css` (which authors fully-styled
structure for **every** manifest component) gets bigger at med/high; (b) verbose aesthetics
(retro-y2k: gradients, multi-borders, shadows, pseudo-elements) inflate per-component CSS
2–3×. Raising the cap is a treadmill: 8192→16384 cleared low, 16384 fails at med, and high
+ a verbose aesthetic will overflow a higher cap too. (We've bumped the default to **32000**
as an immediate stopgap so current runs proceed — but that is *not* the robustness fix.)

The robust fix bounds nothing in the stages and instead makes the **client** complete a
response that exceeds the per-call cap, transparently to every stage (stage 1 JSON, stage 2
delimited, stage 3 `<main>`).

## What to build (in the `GenerationClient` boundary — stages unchanged)

When a Messages API response comes back with `stop_reason == "max_tokens"`, **continue it**
instead of raising:

- **Native assistant-prefill continuation, not a "please continue" prompt.** Re-issue the
  request with the model's partial text appended as a trailing `assistant` message, so the
  model literally continues the same token stream rather than starting a fresh reply (which
  risks a preamble or a restarted `===FILE===` marker). This is the load-bearing detail for
  stability.
- **Concatenate raw** — partial + continuation with **no separator** — and return the joined
  text. Parsing (the `===FILE===` splitter / JSON extractor) runs on the joined string, so a
  seam *inside* a CSS body or JSON string is invisible as long as nothing is duplicated.
- **Guard against duplication / drift.** If a continuation chunk re-opens a `===FILE===`
  marker already present in the accumulated text, or repeats the trailing slice of the
  accumulated text, trim the overlap before joining. (Be mindful the API may strip trailing
  whitespace on the prefill assistant message — the seam may land at a slightly different
  point than the raw cut.)
- **Bound the loop** — at most ~2–3 continuations. If still truncated after the budget,
  raise the existing clear `max_tokens` error (which then drops the site with logging — no
  silent partial artifacts).
- Continuation is a **rarely-exercised safety net**, not the hot path: with the 32000 cap
  the common case stays single-shot and deterministic; continuation only catches the tail at
  genuinely large sites.

## Acceptance criteria

- [x] A response with `stop_reason == "max_tokens"` is transparently continued via
      assistant-prefill and returned as one joined string the existing parsers accept;
      stages call `complete()` unchanged.
- [x] **Seam test**: a known-good stage-2 (`===FILE===`) response is cut mid-`components.css`,
      the continuation completes it, and `parse_design_system` reconstructs all four blocks
      faithfully (no duplicated marker, no repeated/ dropped CSS at the seam).
- [x] A duplicated-overlap continuation (model repeats the tail / re-opens a seen marker) is
      trimmed so the joined output still parses correctly (unit-tested with a stub).
- [x] The continuation loop is bounded; exhausting it raises the existing actionable
      `max_tokens` error (→ drop-with-logging), never returns a partial artifact.
- [x] A truncated-then-continued exchange is simulated with a fake Anthropic client so the
      behavior is covered with no live API call; full suite green (clean `TMPDIR`).
- [x] The stale "stage-2 output is bounded … one call suffices at all complexity levels"
      note in issue 09 is corrected/annotated as superseded by this slice.

## Blocked by

- None — builds on issue 09's `stop_reason` detection already in the client.
