# EP-01 — Persist graded renders (--save-renders default-on)

Status: done (committed 524a165)

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(grill-resolved, decision "`--save-renders` — default-on in emit").

## What to build

The verifier already renders every candidate page in-process to grade it, then
discards those images. Make the grader **persist the exact candidate screenshots
it graded** so reports (and any audit) use the same pixels that produced the
score — faithful (same sealed image + bundled fonts) and free of any local
re-render.

End-to-end behaviour: when a task is graded, each rendered candidate page is
written as a PNG into a `renders/` subdirectory of the verifier output directory
(the dir Harbor persists, alongside `reward.json`). This is **on by default**
with an opt-out, and the **emitted verifier entrypoint carries it by default**, so
every newly-emitted task persists its graded renders with no extra flags. It works
the same in full 4-term and deterministic-only grading (renders are independent of
whether the judge ran). Placement is the verifier output dir (a grading
byproduct), never the agent artifacts dir.

Also fold in a one-line config change unrelated to rendering but batched here: the
generation-batch default concurrency moves from 8 to 10, to match the eval
concurrency default (one consistent number at both ends of the pipeline).

## Acceptance criteria

- [ ] Grading a task writes one PNG per rendered candidate page into a `renders/`
      subdir of the output directory; filenames map cleanly back to pages (via the
      page identity used elsewhere) so a report can pair each with its reference.
- [ ] Render-persistence is **on by default**; an explicit opt-out suppresses it
      (no PNGs written) while grading proceeds normally.
- [ ] A page whose candidate HTML is absent (a missing/zero-scored page) does not
      crash persistence — it is simply skipped (no PNG), consistent with how the
      grader already treats a missing page.
- [ ] Persistence behaves identically in deterministic-only mode (no judge): the
      same candidate PNGs are written.
- [ ] The **emitted verifier entrypoint** runs with render-persistence enabled by
      default (a freshly-emitted task persists graded renders with no extra flag).
- [ ] The generation-batch default concurrency is 10 (was 8).
- [ ] Pure behaviour is unit-tested with a stub judge (no live API/network): renders
      land in the expected place; opt-out suppresses them; deterministic-only still
      persists; emitted entrypoint carries the default. Existing grade/emit tests
      stay green. Full suite green (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None — can start immediately. Independent of EP-02 and EP-03 (disjoint files).
