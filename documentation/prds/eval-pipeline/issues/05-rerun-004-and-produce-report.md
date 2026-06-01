# EP-05 — (HITL) Re-run 004 via launcher → faithful renders + produce the 004 report

Status: ready-for-agent

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(grill-resolved, build order — the integration / loop-closer step).

## What to build

The human-in-the-loop integration slice that ties EP-01..04 together and produces
the first real artifact. The existing `opus47-004` job predates render-persistence,
so it has no `verifier/renders/`; this slice re-runs the reference task through the
launcher (which now refreshes the baked grader to current `--save-renders` code) and
generates the per-task report against the fresh, faithful job.

End-to-end: use the eval launcher (EP-02) to re-run the curated
`local-service / luxury-serif / med` task — Claude Code + Opus 4.7, 10 attempts, 10
concurrency, on Modal, `--force-build` — producing a job whose every trial has
`verifier/renders/` (faithful, in-container, bundled-font pixels). Then run the report
generator (EP-03 + EP-04) against that job to produce the self-contained per-task
`report.html` + normalized scores record, and commit them under the model-eval report
directory as the first committed evidence artifact.

This is a HITL slice: it spends real Modal + API budget (~$20, ~13 min for 10 trials)
and requires a human to drive the run and eyeball the result.

## Acceptance criteria

- [ ] The 004 task is re-run via the launcher (not a hand-typed command); the
      resulting job has `verifier/renders/` populated for its trials (render
      persistence took effect via the refreshed grader + `--force-build`).
- [ ] The report generator produces a complete per-task `report.html` (items 1–7) +
      normalized scores record against that fresh job, with the galleries showing the
      faithful in-container renders.
- [ ] The report + scores record are committed under the model-eval report directory
      as the first committed evidence artifact (rollouts themselves are
      temperature-nondeterministic — commit the output, not byte-repro).
- [ ] A quick eyeball confirms the report's numbers match the run (reward ≈ prior
      ~0.76 ± 0.01 band; content the weakest term) and the galleries render.

## Blocked by

- EP-01 (render persistence), EP-02 (launcher), EP-03 (harvest + tables/plots),
  EP-04 (galleries).
