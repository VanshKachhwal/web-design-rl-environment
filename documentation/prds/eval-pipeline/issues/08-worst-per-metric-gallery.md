# EP-08 — Report item 6: replace the best/worst triple with a "worst per metric" reference-vs-candidate gallery

Status: done

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(visual-evidence galleries, items 6–7). Refines EP-04's item 6; builds on EP-07
(persisted reference renders).

## Problem

The current report item 6 (`_per_metric_gallery_html`) renders a
`reference | best | worst` **triple** per term. It's uninformative because the
three cells **mix pages**: the reference shown is only the *best* render's page,
while the *worst* render is usually a **different** page — so the worst cell has no
matching reference beside it and you can't actually compare target-vs-attempt for
the failure case.

We want item 6 to be a **failure-diagnosis** view: for each metric, the
worst-scoring page shown as a true **same-page reference vs candidate** pair, so you
can see exactly where and how the model did worst on that term.

The "best" side is intentionally dropped from item 6 — the best target-vs-candidate
view already exists as **item 7** (best-overall trial vs reference, all pages), so a
per-metric best is redundant. (The user confirmed: only worst per metric for item 6.)

## What to build

Replace item 6 with a **"Worst per metric"** gallery. For each of the four terms:
- Take the **worst** trial×page on that term (already provided by
  `aggregate_results.per_metric_extrema(scores)[term]["worst"]`, which carries
  `{trial_id, page, score}`).
- Render a same-page **reference | candidate** pair (the same two-cell `pair` layout
  item 7 uses, NOT the three-cell triple): the reference from
  `verifier/reference_renders/<page>.png` for that page+trial (via `_reference_uri`,
  EP-07) and the candidate from `verifier/renders/<page>.png` (via `_render_uri`),
  both for the worst page's trial_id.
- Label the row with the term and annotate the pair with the worst **score** (and the
  page / trial id, matching the existing label style). The range annotation is no
  longer needed (it existed to signal "uniformly good" across the old triple); a
  single worst-score label is the relevant number. Keeping a small range/mean hint is
  optional, not required.

Section heading changes from "Per-metric best / worst (reference | best | worst)" to
something like **"Worst per metric (reference vs candidate)"**.

**Keep item 7 (`_best_overall_gallery_html`) exactly as-is** — it's the best view.

**Minimal, non-breaking:** this is a **report-side** change only.
- Do **not** modify `aggregate_results.per_metric_extrema` — it still returns
  `best`/`worst`/`range`; item 6 simply stops consuming `best` and `range`. Leaving
  the pure function (and its tests) untouched keeps the diff small.
- `_figure_cell` already degrades a missing render to a `(no render)` placeholder, so
  a pre-EP-07 job (no `reference_renders/`) still renders the worst-candidate with a
  placeholder reference cell — no crash. Preserve that.

## Acceptance criteria

- [x] Report item 6 no longer renders a `reference | best | worst` triple; the
      per-metric **best** cell is gone from item 6.
- [x] For each of the four terms, item 6 shows the **worst** trial×page on that term
      as a same-page **reference | candidate** pair (reference and candidate are the
      *same* page, sourced from that page's persisted renders), score-labelled.
- [x] The item-6 section heading reflects "worst per metric" (no "best" in item 6).
- [x] Item 7 (best-overall trial vs reference, all pages) is unchanged.
- [x] `aggregate_results.per_metric_extrema` is unchanged (still returns best/worst);
      no aggregate/test churn there.
- [x] A pre-EP-07 job (candidate renders, no `reference_renders/`) still builds the
      report without crashing — the reference cell degrades to the placeholder.
- [x] The report-rendering unit tests are updated to assert the new worst-only pair
      structure (and that the per-metric best cell is gone); matplotlib/HTML embedding
      stays untested shell. Full suite green (clean `TMPDIR`, Docker render test
      excluded).
- [ ] Faithful end-to-end view: a post-EP-07 re-eval + report regen (HITL) to
      populate `reference_renders/` and visually confirm the rendered gallery — not
      verifiable from unit tests alone.

## Blocked by

- None to build — the selection data (`per_metric_extrema`) and the persisted
  reference renders (EP-07) already exist. Touches `scripts/report.py`
  (`_per_metric_gallery_html` + the item-6 heading in `_galleries_html`) and the
  report tests. The faithful end-to-end view still wants a post-EP-07 re-eval +
  report regen (HITL) to populate `reference_renders/`.
