# EP-02 — Eval launcher (one command to run Opus 4.7 on a curated task)

Status: done (committed 389672e)

## Parent

PRD: `.scratch/eval-pipeline/PRD.md`. Design: `docs/design/eval_pipeline.md`
(grill-resolved, "Harness + parallelization" + the package-refresh decision).

## What to build

A single command that runs the agent-under-test (Claude Code + Opus 4.7) on a
**curated task** N times on Modal, replacing today's manual clone + hand-typed
`harbor run`. Split into a pure, unit-tested core and a thin subprocess shell —
the same pattern as the Modal batch runner.

End-to-end behaviour, given a curated task and run parameters: the launcher

1. **clones** the curated task to a throwaway eval copy (the shipped task is never
   mutated);
2. **refreshes the baked grader package** in the eval copy — clean-overwrites the
   frozen package snapshot with the *current* repo source (clearing the old package
   dir first so a since-deleted module can't linger), so the verifier grades with
   current code, not whatever was frozen at emit time;
3. **flips the agent environment** `allow_internet` to true on the eval copy (so the
   in-sandbox agent can reach the API) — the verifier env is left as-is;
4. **builds and invokes** the Harbor run: agent = claude-code, model = Opus 4.7,
   attempts (default 10), concurrency (default 10), executor = modal, force a fresh
   verifier build, the shared `ANTHROPIC_API_KEY` (from `.env`) passed to both the
   agent and the verifier judge, a job name, and **prints the resulting job path**.

Interactive by default (the human confirms Harbor's host-access prompt); an
unattended flag passes the auto-confirm through. It only **launches** — it does not
wait-and-report (eval and report are decoupled).

## Acceptance criteria

- [ ] Given a curated task path + params, the **argv builder** (pure) produces the
      correct Harbor invocation: claude-code agent, Opus 4.7 model, the attempts and
      concurrency flags (defaults 10/10), modal executor, force-build, the shared key
      wired to agent + verifier, the job name, and the unattended passthrough when set.
- [ ] The **clone-flip-refresh** (pure, on a fixture task, no network): produces an
      eval copy distinct from the source; sets the **agent** env `allow_internet` true
      while leaving the **verifier** env unchanged; and replaces the baked package
      with current source (old package dir cleared first — no stale leftover files).
- [ ] The source curated task is unmodified after a launch is prepared.
- [ ] The launcher loads the shared key from `.env` and prints the resulting job
      path on success.
- [ ] The `subprocess`/Harbor invocation is the (untested) shell; the module stays
      import-safe without Harbor/Modal installed; the pure cores carry the tests.
- [ ] Pure cores unit-tested with fixtures + stubs (no Harbor/Modal/network). Full
      suite green (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None — can start immediately. Independent of EP-01 and EP-03 (disjoint files).
