# EP-04 — Report: visual-evidence galleries (report items 6–7)

Status: done (committed d42a602)

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(grill-resolved, "Report generator (C)", items 6–7).

## What to build

Layer the **visual evidence** onto the report from EP-03, binding the grader's
numbers to screenshots so a reader can *see* what a high vs low score looks like.
Consumes the persisted graded renders (`verifier/renders/` from EP-01) and the
task's baked reference screenshots.

Two galleries added to the self-contained `report.html`:

- **Item 6 — per-metric best/worst gallery (all four terms).** For each of the four
  terms, find the page-render scoring **highest** and **lowest** on that term across
  all trials × pages, and show it beside the **reference** for that page
  (`reference | best | worst`), labelled with the scores. Annotate each pair with its
  score *range*, so a near-identical low-variance pair (e.g. color) reads as
  "uniformly good," not "no signal." Extremes are taken at the trial × page level (a
  concrete screenshot, not a whole-site average).
- **Item 7 — best-overall attempt vs reference, all pages.** Take the single
  highest-`reward` trial and show its render beside the reference for **every** page —
  the "how close can the model get" ceiling visual.

The selection logic (per-metric trial × page extrema; best-overall trial) is pure
and unit-testable on the normalized scores object; loading/compositing the PNGs and
embedding them in the HTML is the untested shell.

## Acceptance criteria

- [ ] `report.html` gains, for **each of the four terms**, a `reference | best | worst`
      page triple with the page's best- and worst-scoring renders on that term,
      score-labelled and range-annotated.
- [ ] `report.html` gains a best-overall section: the highest-`reward` trial's render
      beside the reference for every page.
- [ ] The **selection logic** (per-metric trial × page best/worst; best-overall trial)
      is pure and unit-tested on the normalized object.
- [ ] Galleries source candidate pixels from the job's persisted `verifier/renders/`
      and the reference from the task's baked reference screenshots (the exact images
      the grader compared); images are embedded (report stays self-contained).
- [ ] Image loading/compositing/HTML embedding is the untested shell; full suite green
      (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- EP-03 (extends its `report.html` + normalized scores object). Faithful end-to-end
  verification additionally needs persisted renders (EP-01 + a re-run, EP-05), but the
  gallery code is testable against a fixture job that includes renders.
