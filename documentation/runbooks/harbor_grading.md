# Harbor grading runbook (oracle + live 4-term judge)

How to run an emitted task through the Harbor pipeline on Modal and read its
reward. Companion to [`modal_batch.md`](./modal_batch.md) (which produces the
tasks). `harbor` is installed at `~/.local/bin/harbor`.

## What an emitted task grades by default

Every task emitted by `webdesign_rl.emit` ships a `tests/test.sh` that runs the
grader CLI in **full 4-term mode** — `structure`, `color`, `content`, and the
live **`design_judge`** (LLM) term. The judge needs:

- `ANTHROPIC_API_KEY` in the verifier env — wired in `task.toml`
  (`[verifier.env] ANTHROPIC_API_KEY = "${ANTHROPIC_API_KEY}"`, substituted from
  your shell), and
- `allow_internet = true` on the verifier env (already set in `task.toml`).

To grade **deterministic-only** (three terms, no key, no egress — e.g. offline
or zero-cost CI), add `--no-judge` back to the task's `tests/test.sh`.

## Run a task (oracle agent, Modal, live judge)

```bash
cd /Users/vansh/Code/open_source/web-design-rl-environment

# Export ANTHROPIC_API_KEY so Harbor can resolve ${ANTHROPIC_API_KEY} in task.toml
set -a; source .env; set +a
echo "ANTHROPIC_API_KEY length: ${#ANTHROPIC_API_KEY}"   # expect non-zero

modal profile current                                    # confirm Modal auth

# Oracle agent (runs solution/ as the candidate) on Modal, force a fresh build
~/.local/bin/harbor run \
  -p ./out/curated/<seed_id>/task \
  -a oracle -e modal --force-build

~/.local/bin/harbor view                                 # per-term reward table
```

- `-a oracle` runs `solution/solve.sh` (copies `solution/site` → the agent's
  `/logs/artifacts`), then the **separate** verifier renders that and grades it
  against the baked reference. Since the oracle candidate *is* the reference, a
  well-posed task ceilings: deterministic terms ≈ **1.000**, `design_judge`
  ≈ **0.99** (near-ceiling with a sliver of slack — a judge pinned at exactly
  1.000 couldn't discriminate, so this is the healthy outcome).
- `--force-build` cold-builds the verifier image on Modal the first time
  (Chromium + font palette, a few minutes); later runs reuse it.

### Validated reference result

`004_local-service_luxury-serif_med`, oracle + live judge (2026-05-31):

| structure | color | content | design_judge | reward |
|---|---|---|---|---|
| 1.000 | 1.000 | 1.000 | 0.986 | 0.996 |

This confirms both the task's oracle ceiling and the live-judge path on Modal.

## Notes / gotchas

- The `litellm` botocore warnings and the `Sandbox.filesystem` deprecation line
  in the run output are harmless (litellm probing unused Bedrock/SageMaker
  backends; a Harbor-internal deprecation).
- The judge model is **Sonnet 4.6** (deliberately ≠ the Opus agent under test —
  avoids self-preference bias).
- Local deterministic-only oracle without a key (quick check, no Modal):
  `PYTHONPATH=src .venv/bin/python -m webdesign_rl.grade --candidate <site>
  --reference-site <site> --page-map <pm> --out <dir> --no-judge`.

## Downstream: the Opus 4.7 eval (brief deliverable, not built yet)

Swapping `-a oracle` for the Claude Code + Opus 4.7 agent adapter and running it
~10× per task is the brief's results deliverable (run the model → grade each
rollout → visualize the spread → surface failure patterns). The grading path
above is exactly what it reuses; only the agent changes. See the eval-harness
stubs under `eval/` + `scripts/{evaluate,report}.py`.
