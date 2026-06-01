# PRD: Eval + Reporting Pipeline (Opus 4.7 on generated tasks)

Status: ready-for-agent

> Scope: the **evaluation harness** that runs the agent-under-test (Claude Code +
> Opus 4.7) on the **curated tasks** the generator produces, persists the graded
> screenshots, and turns a Harbor job into an automated per-task evidence report.
> The grader (4-term), render module, Harbor emit packaging, and the generator are
> already built and are *consumers/producers* around this, not part of this PRD.
> Grounded in `docs/design/eval_pipeline.md` (grill-resolved build contract,
> 2026-05-31) and validated against the real `opus47-004` job. The hand-written
> narrative results README is a *downstream deliverable*, **out of scope** here.

## Problem Statement

We can generate well-posed tasks and grade a candidate through Harbor, but the path
to the brief's **results deliverable** — "run Claude Code with Opus 4.7 **10 times**
on a task, show how the grader scores the attempts, argue why higher reward = better
replication, and surface what the model struggles with" — is **hand-glued and
lossy**:

- Launching an eval means cloning a task by hand, flipping `allow_internet`, and
  typing a long `harbor run` command from memory.
- The verifier renders the candidate to grade it, then **throws those screenshots
  away** — so any report must re-render locally (host fonts, slow, infidelity).
- Worse, the task's verifier image **bakes a frozen grader snapshot at emit time**,
  so a re-run silently grades with *stale* code.
- Reading results means hand-parsing `result.json` and per-trial JSON; there is no
  artifact a reviewer can open to see "how the grader scored the 10 attempts."

The result is that the single most important question the brief asks — *is this
reward a faithful teacher?* — has no repeatable, shareable evidence pipeline behind
it. We need the eval to be one command, the graded pixels to be persisted, and a
Harbor job to turn into a self-contained per-task report automatically.

## Solution

Three composable pieces, all reusing what already exists:

1. **An eval launcher** — one command takes a curated task and runs Claude Code +
   Opus 4.7 on it N times on Modal. It clones the task to a throwaway eval copy,
   **refreshes the baked grader package to current code** (killing the staleness
   gotcha), flips the *agent* environment to `allow_internet=true` (so the in-sandbox
   agent can reach the API — the shipped task stays offline), loads the shared key
   from `.env`, and invokes Harbor with the right flags. It prints the resulting job
   path. It does **not** wait-and-report (decoupled).

2. **Persisted graded renders** — the grader gains a default-on option to write the
   exact candidate screenshots it rendered for grading into the verifier output dir.
   Because Harbor persists that dir, every trial's *graded pixels* land in the job
   automatically — faithful (same sealed image + bundled fonts as the score), with no
   re-render and no host-font mismatch.

3. **A report generator** — pointed at any saved Harbor job, it harvests the job +
   per-trial term files + persisted renders into a normalized, auditable
   scores record, and emits a **self-contained per-task HTML report**: the score
   distribution across the trials, the per-term and per-page breakdown, and visual
   galleries that bind each metric (and the best overall attempt) to the reference.
   This automated report is the *evidence dashboard*; a human writes the narrative
   results README on top of it later.

Net: `evaluate` (launch) → Harbor runs on Modal, persisting graded renders →
`report` (from the saved job) → a per-task `report.html` + scores record. One
discoverable flow, faithful artifacts, no manual glue.

## User Stories

1. As a researcher, I want to launch a 10×-Opus-4.7 eval on a curated task with a
   single command, so that I don't reconstruct a long `harbor run` invocation by hand.
2. As a researcher, I want the launcher to clone the task to a throwaway eval copy,
   so that the shipped/curated task is never mutated by an eval run.
3. As a researcher, I want the eval copy's agent environment flipped to
   `allow_internet=true` automatically, so that the in-sandbox Claude Code agent can
   reach the model API while the committed task stays offline by design.
4. As a researcher, I want the launcher to refresh the eval copy's baked grader
   package to the current repo code, so that the verifier grades with the grader I
   have now — not whatever was frozen at emit time.
5. As a researcher, I want the launcher to read the shared `ANTHROPIC_API_KEY` (and
   Modal creds) from `.env`, so that I never export keys manually before a run.
6. As a researcher, I want to set the number of attempts (default 10), the
   concurrency (default 10), the model, the executor, and the job name as flags, so
   that I can tune a run without editing code.
7. As a researcher, I want the launcher to pass the shared key to both the agent and
   the verifier judge, so that one key drives the whole run.
8. As a researcher, I want the launcher to force a fresh verifier build, so that the
   refreshed grader code actually ships into the image.
9. As a researcher, I want the launcher to print the resulting job path, so that I can
   hand it straight to the report generator.
10. As a researcher, I want an unattended flag to auto-confirm Harbor's host-access
    prompt, so that I can script runs, while the default stays interactive.
11. As a grader author, I want the grader to persist the exact candidate screenshots
    it rendered for grading, so that reports show the pixels that produced each score.
12. As a grader author, I want render-persistence on by default in emitted tasks with
    an opt-out, so that every future eval run carries its graded screenshots without
    extra flags.
13. As a grader author, I want the persisted renders written to the verifier output
    dir (not the agent artifacts), so that Harbor persists them and the semantics stay
    clean (grading byproduct, not agent-authored output).
14. As a grader author, I want render-persistence to work in both 4-term and
    deterministic-only modes, so that it never depends on whether the judge ran.
15. As a researcher, I want to point a report command at any saved job directory, so
    that I can regenerate a report without re-running the expensive eval.
16. As a researcher, I want the harvest step to read each trial's term file as the
    source of truth (and the job result only for run metadata), so that a dynamic
    eval key in the job result never breaks parsing.
17. As a researcher, I want a normalized scores record (machine-readable + tabular)
    written alongside the report, so that the report is regenerable and auditable, and
    future cross-task analysis has one parser.
18. As a reviewer, I want a provenance header on the report (task id, seed tuple,
    model, executor, trial count, cost, tokens, wall-clock, date, commit), so that the
    run is auditable and the distribution/complexity claims are grounded.
19. As a reviewer, I want a per-trial score table with summary stats
    (median / mean ± std / min / max), so that I can see how the grader scored every
    attempt at a glance.
20. As a reviewer, I want a reward distribution plot plus per-term distributions, so
    that I can judge the spread and reliability of the reward signal.
21. As a reviewer, I want per-term mean bars, so that I can read the model's skill
    shape (e.g. strong color, weak content) immediately.
22. As a reviewer, I want a per-page × per-term heatmap, so that I can localize where
    the model is weak (which pages, which terms).
23. As a reviewer, I want, for each of the four terms, the best- and worst-scoring
    page render shown beside the reference, so that each metric is bound to a concrete
    visual and I can see what a high vs low score on that term looks like.
24. As a reviewer, I want each gallery pair annotated with its score range, so that a
    near-identical low-variance pair (e.g. color) reads as "uniformly good," not "no
    signal."
25. As a reviewer, I want the single best-overall attempt shown against the reference
    across every page, so that I can judge how close the model can actually get.
26. As a reviewer, I want the report to be a single self-contained HTML file, so that
    I can open and share it without a server or asset directory.
27. As a researcher, I want the eval and report stages decoupled, so that a report
    template fix never forces a re-run of the expensive eval.
28. As a researcher, I want the generation batch concurrency raised to 10 to match the
    eval concurrency, so that both ends of the pipeline use one consistent default.
29. As a maintainer, I want the pure cores (argv building, clone-flip-refresh, harvest,
    plot-data computation) unit-tested with no Harbor/Modal/network, so that the logic
    is verifiable offline and only the thin shells stay untested.
30. As a researcher, I want the report generator to assume persisted renders are
    present (single faithful source), so that it stays simple and never silently falls
    back to an infidelitous local re-render.
31. As a future maintainer, I want the harness to live behind clear module seams
    (launch vs harvest vs render-the-report), so that it can later slot under a unified
    pipeline CLI without rework.

## Implementation Decisions

- **Three modules, disjoint surfaces.**
  - **A — render persistence**: a default-on capability in the grader CLI + the core
    `grade()` function that writes each rendered candidate page into a `renders/`
    subdir of the verifier output dir, plus an opt-out flag; the emitted verifier
    entrypoint carries it so it ships by default. Touches the grader and emit
    template/tests. Also folds the generation-batch concurrency default 8 → 10.
  - **B — eval launcher**: a wrapper plus a thin CLI. The wrapper's responsibilities,
    in order: clone curated task → throwaway eval copy; **refresh the baked grader
    package** (clean-overwrite the frozen snapshot with current source via the
    existing copy helper — clear the old package dir first so a since-deleted module
    can't linger); flip the agent env `allow_internet` to true; build the Harbor
    invocation (agent = claude-code, model = Opus 4.7, attempts default 10,
    concurrency default 10, executor = modal, force-build, shared key to agent +
    verifier, print job path); invoke it. Interactive by default with an unattended
    passthrough.
  - **C — report generator**: a harvester plus a report CLI. The harvester is a pure
    function (job dir → normalized scores object): run metadata from the job result;
    per-trial aggregate + four terms + per-page terms + judge sub-scores from each
    trial's term files (the per-trial files are the **source of truth**, since the
    job-result eval key is dynamic). It persists the normalized scores as a
    machine-readable record + a tabular export, then renders a self-contained HTML
    report consuming **only** the normalized object + the persisted render PNGs +
    the task's baked reference screenshots.
- **Decoupled launch vs report** — `evaluate` only launches and prints the job path;
  `report` runs separately against any saved job. Mirrors the `modal_batch` (launch)
  vs `validate_grader` (report) split already in the repo.
- **Harvest contract** — a normalized scores record is the single seam between "parse
  the messy job dir" and "render the report"; everything downstream reads only it.
- **Agent internet is granted on the eval copy only** — the shipped/curated task and
  the emit template keep the agent env offline; the verifier env stays internet-on for
  the judge (unchanged).
- **Render-persistence placement** — the verifier output `renders/` dir (a grading
  byproduct), never the agent artifacts dir; relies on Harbor persisting the verifier
  output, so no extra artifact-download flag is needed.
- **Report contents = items 1–7 (locked):** provenance header; per-trial score table +
  summary stats; reward distribution + per-term distributions; per-term mean bars;
  per-page × per-term heatmap; per-metric best/worst-vs-reference gallery for **all
  four** terms (extremes taken at the trial×page level, score-range annotated);
  best-overall-attempt-vs-reference across all pages.
- **Concurrency = 10 at both ends**, one shared key (the deliberate moderate cap under
  a single key's rate limit; scale only if errored-trial count stays zero).
- **Build order**: A and B are independent (disjoint files) and build in parallel;
  then a re-run of the reference task via the launcher produces faithful persisted
  renders; then C is built against that job.

## Testing Decisions

- **What makes a good test here**: exercise *external behavior* of the pure cores with
  fixtures and stubs, never the thin I/O shells. No live Harbor, Modal, network, or
  API calls in tests.
- **A — render persistence**: a `grade()` run with a stub judge writes the expected
  per-page render PNGs into the output `renders/` dir; the opt-out suppresses them;
  the emitted verifier entrypoint contains the persistence behavior by default;
  deterministic-only mode still persists. Prior art: the existing grader and emit
  tests.
- **B — eval launcher pure core**: the **argv builder** produces the correct Harbor
  invocation for given params (agent/model/attempts/concurrency/executor/force-build/
  job-name/keys/unattended); the **clone-flip-refresh** correctly clones a fixture
  task, sets the agent env internet flag true (verifier untouched), and replaces the
  baked package with current source (old package cleared first). The `subprocess`
  invocation of Harbor is the untested shell. Prior art: `modal_batch`'s pure-core /
  thin-Modal-wrapper split.
- **C — report generator pure core**: the **harvester** turns a fixture job dir into
  the normalized scores object (correct per-trial/per-term/per-page values, summary
  stats, run metadata; robust to the dynamic eval key by reading per-trial files); the
  **plot-data computations** (distribution series, per-term means/std, per-page×term
  matrix, per-metric trial×page extrema, best-overall selection) are pure and tested
  on the normalized object. The matplotlib rendering, base64 embedding, and HTML
  assembly are the untested shell. Prior art: `validate_grader.py` (headless Agg
  plots + committed report) and `grade/study.py` (pure stats helpers).
- **Modules to unit-test**: A's persistence behavior, B's argv-builder +
  clone-flip-refresh, C's harvester + plot-data computations. Shells (subprocess,
  matplotlib/HTML, the Harbor/Modal run itself) are deliberately untested.

## Out of Scope

- **The narrative results README** (`reports/model-eval/README.md`) — hand-written
  per task *after* reading the automated reports; selects the curated killer example,
  the validity backbone, and the cross-task synthesis. The harness only produces the
  evidence it draws from.
- **The validity argument's construction** — it is a README-time, no-new-runs
  synthesis (perturbation ladder already built + oracle(=reference, ~0.996)-vs-Opus
  (~0.76) coarse gap + within-Opus worst-vs-best fine-grained check). The harness
  surfaces the raw evidence; it does not author the argument or run new baselines.
- **Deferred report elements**: page-presence/completeness table; inter-term
  correlation matrix; caveats footer; auto text word-diff; `--oracle-job` distribution
  overlay. Revisit after the first real report exists.
- **ATIF / agent-trajectory analysis** (turns/tokens/iteration behavior).
- **Multi-task / dataset runs** in one job, and a fused `run-all` command — the
  launcher takes a single task for v1.
- **The unified pipeline CLI / packaging** (single `webdesign-rl` console tool,
  workspace conventions, manifest) — parked in `docs/design/package_design.md`; the
  modules here are built so they can later slot under it.

## Further Notes

- **Validated against a real run.** The `opus47-004` job (Opus 4.7 ×10 on the
  `local-service / luxury-serif / med` curated task) already exists and is the
  reference fixture for shaping these modules: reward 0.757 ± 0.011 (tight → reliable
  signal), `content` the bottleneck (~0.55, degrading with prose density — pricing
  0.82 → gallery 0.40), `color` ~0.97; oracle on the same task ~0.996 (healthy
  oracle↔agent gap); ~$2 and ~13 min per trial. Because that job predates render
  persistence (A), the reference task is re-run via the launcher (B) — which refreshes
  the baked grader — to produce faithful `verifier/renders/` for C to consume.
- **Why decoupled + persisted renders is the right backbone**: we grade and report on
  the *same pixels in the same sealed environment*, so the visual evidence and the
  scalar reward can never drift — that methodological tightness is the report's
  credibility.
- Full grill-resolved decision log lives in `docs/design/eval_pipeline.md`.
