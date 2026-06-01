# Eval Pipeline Design

> Status: **built** — the single-task report ships (items 1-7, two output formats;
> the richer panels are deferred, see *Report contents*). This is the brief's *results*
> deliverable — run Claude
> Code (Opus 4.7) on the generated tasks, grade each attempt with our 4-term
> grader, and produce a **visual report** that (a) shows how the grader scores the
> attempts, (b) argues *why higher reward = better replication*, and (c) surfaces
> the patterns the model struggles with. Downstream of generation + emit; reuses
> [`grader_design.md`](./grader_design.md) and the Harbor packaging unchanged.
> Companion ops runbook: [`../runbooks/harbor_grading.md`](../runbooks/harbor_grading.md).

## Why this exists (brief deliverable)

The project brief asks for "a **visual report of results**: running Claude Code
with Opus 4.7 **10 times** on a task, how well does the grader score the results?
Explain **why higher grades correspond to better design replications**" plus
"**common patterns the model struggles with**". This doc owns the design of the
pipeline that produces that report.

## What's validated so far (2026-05-31)

A first real run exists: **`004_local-service_luxury-serif_med`, Opus 4.7 ×10 on
Modal** (`jobs/opus47-004/`). Everything below is observed, not assumed.

- **Mechanism = Harbor-native, no custom orchestration of the runs.** Claude Code
  is a built-in agent adapter; the brief's "10 times" is the `-k 10` flag:
  `harbor run -p <task> -a claude-code -m claude-opus-4-7 -e modal -k 10 -n 5
  --ae ANTHROPIC_API_KEY=$… --artifact /logs/artifacts`. The agent env needs
  `allow_internet = true` (the agent calls the API to think); the verifier stays
  as emitted (judge-on). So the harness is **harvest → aggregate → visualize →
  analyze**, not "drive the model".
- **Data on disk per job** (`jobs/<job-name>/`):
  - `result.json` — **job-level** (`JobResult`): `stats.evals.<agent>__<model>__adhoc.metrics`
    is the list of per-trial metric dicts; also carries token usage + `total_cost_usd`.
  - `task__<id>/verifier/reward.json` — the 5 flat terms for that trial.
  - `task__<id>/verifier/reward-details.json` — **per-page** `structure/color/content/design_judge`
    + the judge's `design_judge_sub_scores` (`layout_alignment`, `color_palette`,
    `typography`, `content_completeness`).
  - `task__<id>/artifacts/` — the agent's produced HTML/CSS (renderable → gallery).
  - `task__<id>/result.json` — **trial-level** (`TrialResult`): agent/verifier
    results, trajectory, `step_results` (different schema from the job-level one).
- **Result (004 ×10):** reward median 0.758 / mean 0.757 / **std 0.011** (tight →
  reliable signal). Term shape: color 0.97 ≫ structure ≈ judge ~0.75 ≫ **content
  0.55** (the bottleneck). Oracle scored 0.996 on the same task → a healthy
  oracle↔agent gap (the grader discriminates). Compute: ~$20.6 / 10 rollouts.
- **Dominant failure pattern:** content fidelity degrades with prose density —
  structured/label pages (pricing 0.82, index 0.75) reproduce well; prose-heavy
  pages (gallery 0.40, about 0.45, services 0.47) don't. Qualitatively (about
  page, checked by hand) the model reproduces the *scaffold* — nav, headings,
  stat block — but **paraphrases / shortens the body copy** (801→636 words,
  "two decades"→"a decade", "Client Satisfaction"→"Client Retention"). Likely
  causes: it's given pixels not text and generation (not transcription) is its
  native mode; visual-salience bias (big/high-contrast text copied, dense prose
  approximated); semantic-substitution drift; length/effort truncation; and the
  "replicate the *design*" framing nudging effort toward look over verbatim text.
  Cross-method agreement (OCR `content` **and** the LLM judge's
  `content_completeness`/`typography` sub-scores both low, `color` high) is itself
  validity evidence.

## Notes / decisions for later

- **Make the primary reward key unambiguous for Harbor/RL.** Our `reward.json` is
  a flat dict of five keys (`color`, `content`, `design_judge`, `reward`,
  `structure`). Harbor stores all five as independent metrics and does **not**
  know `reward` is the canonical aggregate — the viewer's job-list headline even
  renders the alphabetically-first metric (`color` ≈ 0.97), which misreads as "the
  score" when the real aggregate `reward` is 0.757. *Cosmetic in the viewer; a
  real hazard for RL* — if reward extraction grabs the wrong scalar, training
  optimizes `color` (≈flat, useless) instead of the discriminating 4-term reward.
  When we wire RL, make the canonical reward explicit (configure Harbor's reward
  key to `reward`, or emit the aggregate as the single primary metric with the
  four terms as sub-details). Keep all four terms exposed for the report's
  transparency. *(Out of scope for the single-task report; captured so it isn't
  lost.)*
- **`harbor view` is a web UI, pointed at the `jobs/` parent.** `harbor view jobs/`
  (not a single job dir — that mis-parses the trial dirs as jobs) → open the
  printed `http://127.0.0.1:80xx`. It's for eyeballing one trajectory
  interactively; the report's data source is the JSON above, read directly.
- **Keep the agent env offline by design — flip internet only for the CLI-agent
  eval, never globally.** The committed/curated tasks and the emit template keep
  `[environment] allow_internet = false`. Reasons: (1) the task artifact encodes a
  correctness claim — a faithful replication of a CSS-drawable-only site needs
  *zero* internet, and offline removes the asset-fetch / look-up-the-real-site
  cheating vector; (2) **RL training doesn't need it** — the policy's forward
  passes run in the trainer and the sandbox only executes tools, so offline is
  exactly right for the environment's primary purpose; (3) internet is needed by
  **one path only** — the interactive *Claude-Code-CLI-as-agent* eval, where the
  agent calls the Anthropic API from **inside** the sandbox. Handle that at eval
  time: clone the task to a throwaway copy with `allow_internet = true` (what
  `out/eval/004` does), or override via a Harbor `--config` JobConfig — do **not**
  change the emit default or the shipped fixtures. If the per-eval flip gets
  tedious, the fix is a small clone-and-flip eval-prep helper, not a new default.
  Hermeticity at *grade* time is independently enforced (offline-rendered
  candidate + static-only gate), so granting authoring-time egress doesn't leak
  into the score.

## Report contents

> **What shipped (v1):** `scripts/report.py` emits the per-task report with **items
> 1–7** — provenance, score table, reward + per-term distributions, per-term means,
> per-page × per-term heatmap, the **worst-per-metric** gallery (reference vs candidate),
> and the **best-overall** gallery (all pages) — in **two formats**: a self-contained
> `report.html` and a GitHub-renderable `report.md` + PNG files (`--format`, swept across
> a jobs dir by `scripts/report_all.py`). The richer elements designed below —
> auto-narrative summary, diff/overlay, cross-method scatter, reward-decomposition
> waterfall, weak-baseline arm, and ATIF/trajectory — are **deferred**; the full design
> is kept so the reasoning stays visible.

The report is **an argument that our reward is a faithful RL signal** — not a
results dump. The brief is explicit: "the model learns the grading logic — bad
grading just injects noise." So every element below serves one of the brief's
three questions: *how does the grader score the attempts? why does higher reward
= better replication? what does the model struggle with?* Form factor: a per-task
report under `reports/model-eval/<task>/` — either a self-contained `report.html`
(base64 images + plots) **or** a GitHub-renderable `report.md` + PNG files —
mirroring the committed `reports/grader-validation/` deliverable.

**The critical constraint that shapes everything:** a strong model on one task
produces ~identical attempts (004 ×10: reward 0.731–0.773, std 0.011). That
near-zero variance makes a within-model "rank the 10, see them get better"
monotonicity claim *degenerate* — reviewers would (rightly) call the differences
noise. So the validity argument must use **deliberately-spanned quality**, not the
Opus rollouts alone:
- lean on the already-built **grader-validation report** for controlled synthetic
  monotonicity (perturbation severity → reward);
- engineer a real spectrum on the task — **oracle (≈1.0) + Opus (~0.76) + a weaker
  baseline (~floor)** — so the ranked gallery shows a *visible* gradient;
- present within-Opus micro-variance **honestly** as a secondary signal near the
  noise floor, never as the main evidence.

**Persist the graded screenshots so reporting is faithful *and* fast.** The grader
already renders the candidate in-process (`render_site` → `{page: PIL.Image}`) and
discards it. Add a `--save-renders` flag to the grade CLI → `grade()` writes each
rendered candidate page to `<out>/renders/<page>.png`. Because the verifier writes
to `/logs/verifier` and **Harbor persists that dir** to `task__*/verifier/`, the
graded PNGs land in the job automatically — no re-render, no `--artifact`. This
beats local re-rendering: the persisted PNG is the *exact in-container render with
bundled fonts that was scored*, so the gallery can't conflate a host-font mismatch
with a model error. Placement: `verifier/renders/` (a grading byproduct), **not**
the agent's `artifacts/` (raw authored HTML). It's a small change — grade CLI flag
+ `grade()` save + one line in the emitted `test.sh` — to fold into emit so every
future run carries its graded screenshots. (The existing `opus47-004` job predates
it, so its gallery needs a one-off local re-render.)

**Sections / elements (each tagged with the brief question it answers):**

- **Provenance header** *(audit)* — task id, **seed tuple**, model, env, repo
  commit, date, cost/compute ($20.6 / 10 rollouts). Makes the
  distribution/complexity claims auditable, not asserted.
- **Auto-narrative summary** *(all)* — a templated prose paragraph that fills in
  the numbers *and the detected failure pattern*, so the report reads as analysis.
- **Score table** *(Q1)* — trials × {reward + 4 terms} + a summary row
  (median / mean ± std / min / max); sortable. Headline is the *tightness*
  (reliable signal), not the mean.
- **Reward distribution + per-term bars** *(Q1)* — box/strip of the 10 rewards,
  anchored by the oracle ceiling and a floor; per-term means with spread.
- **Validity panel** *(Q2 — centerpiece)* — (a) reference to the synthetic
  monotonicity ladder; (b) the **quality-spanned ranked gallery** (oracle / Opus /
  weak, beside the reference); (c) **score↔visual binding** — for each metric show
  the *worst page for that metric beside the reference*, so "content = 0.40" is
  physically paired with the page that earned it; (d) **diff / 50%-overlay** of
  candidate vs reference (trivial with persisted renders) — on `about` it lights
  up exactly the paraphrased text blocks; (e) **cross-method agreement** scatter
  (OCR `content` vs judge `content_completeness` per page) + a reward-decomposition
  waterfall.
- **Failure analysis** *(Q3 — the payoff)* — per-page heatmap (content collapses on
  prose-heavy pages, flat elsewhere); the prose-density curve (pricing 0.82 →
  gallery 0.40) with a `page | reference word-count | content` table; judge
  sub-score profile; the `about` reference-vs-attempt diptych with diverging text
  highlighted; the ranked list of *causes* (pixels-not-text, generation-not-
  transcription, salience bias, "replicate the design" framing).
- **Behavior/trajectory summary** *(Q3, if we tap ATIF)* — turns, tokens, whether
  it inspected each screenshot / iterated; can reveal *why* text suffers.
- **Limitations, owned not hidden** — single task (so far); judge k=1 variance;
  OCR noise in `content`; and the **design-taste tension**: is verbatim text the
  right thing to reward in a *design* task? The model's paraphrasing is arguably
  sensible behavior `content` penalizes — we keep the term (it discriminates and
  text *is* part of a faithful copy) but surface the tradeoff.
- **Decision trail** *(taste)* — short pointers to the design docs (why 4 terms,
  equal weight, Sonnet-as-judge ≠ Opus-under-test, the reward-key/RL note); link,
  don't re-explain.

**Deliberately left out** *(taste = subtraction)*: a single "consolidated score" as
the headline (report it as one row, not the story); `pass@k` (meaningless for a
continuous reward); any chart that doesn't answer one of the three questions;
token/cost as anything more than a one-line footnote.

**A framing worth narrating in the report:** we grade and report on the *same
pixels in the same sealed environment*, so the visual evidence and the scalar
reward can never drift — methodological tightness is itself a research-taste
signal.

## Harness + parallelization (decided)

**Eval CLI wrapper — stop typing the mega-command.** A thin shell over
`harbor run`, the same split `modal_batch` has over `modal`:
`scripts/evaluate.py` (CLI) → `eval/run_claude_code.py` (wrapper). Params:
`--task out/curated/<seed_id>`, `--attempts` (→ `-k`, default 10),
`--concurrency` (→ `-n`), `--model claude-opus-4-7`, `--executor modal`,
`--name` (→ `jobs/<name>`). It (1) clones the task → `out/eval/<id>` and flips
`allow_internet=true` (the agreed eval-prep — never touches the shipped task),
(2) loads the key(s) from `.env`, (3) constructs + invokes the full `harbor run`
argv, (4) prints the `jobs/<name>/` path. **Testable core** (no Harbor/network):
the argv-builder and the clone-and-flip — pure functions, unit-tested; the
`subprocess` invocation is the untested shell, exactly like `modal_batch`'s split.

**Parallelization policy.** Concurrency is bounded by the **Anthropic rate limit**,
not Harbor/Modal. Evidence from `opus47-004`: ~27 min for 10 trials at `-n 5`
(2 waves) → ~13 min/trial, ~$2/trial, ~41k output tok/trial (~3.2k OTPM/session;
~1.36M *cached* input/trial so ITPM isn't the bottleneck). So `-n 20` over a
2-task dataset finishes ~one trial-duration (~13 min) — the "2 tasks at once"
speedup. **Decided policy: concurrency = 10 at both ends** — generation
(`modal_batch.DEFAULT_CONCURRENCY` 8 → 10) and eval (`-n 10`). One shared
`ANTHROPIC_API_KEY` serves both the agent (Opus) and the judge (Sonnet), so 10
is the deliberate moderate cap that keeps agents + judges under the single key's
rate limit; scale only if `n_errored_trials` stays 0 and headroom is confirmed
(429s surface as errored/retried trials). Run multiple tasks as **one job over a
dataset** with `-k 10 -n 10` (one `result.json`, one report input). Modal scales
the sandboxes (agent+verifier per trial) fine. (A second key could later split
agent vs verifier load, but we standardize on one shared key for now.)

**`--save-renders` — DECIDED: default-on in emit.** Grade CLI gains `--save-renders`
(on by default, `--no-save-renders` to disable); `grade()` writes each
`rendered[page]` → `<out>/renders/<page>.png`; the emitted `test.sh` carries it;
emit/grade tests updated. Because Harbor persists the verifier `--out` dir, the
exact graded screenshots land in `task__*/verifier/renders/` automatically — no
re-render, no `--artifact`, no host-font mismatch. Placement is `verifier/renders/`
(grading byproduct), not the agent's `artifacts/`.

## Resolved in grill (2026-05-31) — the build contract

The deliverable framing and every open branch were settled in a grill session.
The reviewer who reads the output is a **time-boxed research-trial grader** asking
three things — *is the reward valid? are the sites good/varied? does this person
have taste?* They read an **argument**, not a pile of auto-generated stats. That
drives the central split below.

1. **Two artifacts, not one.** The **deliverable is a single curated narrative**
   (`reports/model-eval/README.md`, same committed-narrative pattern as
   `reports/grader-validation/README.md`) — written **after** seeing real results,
   selecting the most convincing evidence. The **harness is the evidence
   generator** beneath it: per-task drill-down `report.html` + normalized
   `scores.json`. Don't confuse the tool's output with the deliverable; building
   only per-task dumps would force the reviewer to synthesize, which reads as
   *absence* of taste.
2. **Launch/report decoupled.** `scripts/evaluate.py` launches (`harbor run`);
   `scripts/report.py jobs/<name>/` reports from any saved job. Harbor runs are
   long/expensive/HITL, and the report must be regenerable from a saved job without
   re-evaluating. Mirrors `modal_batch` (launch) vs `validate_grader.py` (report).
3. **Harvest contract = persisted `scores.json` + `scores.csv`.** Harvest is a pure
   function (raw job dir → normalized object): job meta (model/agent/n/cost) from
   `result.json`, per-trial aggregate + 4 terms + per-page + judge sub-scores from
   each `task__*/verifier/reward.json` + `reward-details.json` (the **per-trial
   files are the term source-of-truth** — the job-level eval key is dynamic, e.g.
   `claude-code__claude-opus-4-7__adhoc`). Plotting/HTML reads only the normalized
   object. This is the unit-test seam.
4. **Validity argument (README-time) uses existing artifacts — NO new weak runs.**
   Within-Opus variance is tiny (std 0.011), so a within-model "rank 10, see them
   improve" claim is degenerate on its own. Three legs from assets we already have:
   (a) the **perturbation ladder** (`reports/grader-validation/`) — controlled
   monotonicity, the cleanest proof; (b) **oracle (=reference, 0.996) vs Opus
   (~0.76)** — the *coarse, visibly different* gap; (c) **within-Opus worst-vs-best**
   as a fine-grained sensitivity check (it is *systematic* — `content` +0.110 across
   *every* page, not noise — but visually subtle, so supporting, not load-bearing).
5. **Per-task drill-down content** (the auto-report, lightly narrated): score table
   + distribution + per-term; best-vs-worst gallery; per-page heatmap; failure
   characterization. Worst-vs-best lives **here** as the sensitivity check. Because
   the worst→best delta is content/text-driven (layout looks alike), the gallery
   pairs **full-page screenshots** (prove layout/color preserved) **with text
   excerpts** (reference vs best vs worst copy) on the **highest-Δ pages** (services
   Δ+0.20, index Δ+0.16 — not gallery Δ+0.09); an OCR word-diff *overlay* is a v2
   upgrade.
6. **`--save-renders` first, then re-run 004 (option A).** Build `--save-renders`
   default-on; **refresh 004's baked grader package** (the verifier image bakes the
   package at emit time, so the new code only ships via a package refresh +
   `--force-build` — reference screenshots are NOT re-rendered) → re-run the 004
   eval → faithful `verifier/renders/`. The report generator then assumes renders
   are present (single faithful source, no local-render fallback, no host-font
   caveat).
7. **Failure analysis heuristic for v1** (weakest term/page, prose-density from
   reference word counts — deterministic + unit-testable); **ATIF/trajectory
   deferred** (turns/tokens summary is a v2 nice-to-have).
8. **Commit policy.** Commit the report artifacts (README, per-task `report.html`,
   `scores.json`/`csv`, plot PNGs); rollouts are temperature-nondeterministic so we
   *commit the output*, not byte-repro — same philosophy as the curated-10 fixtures.

## Build order

- **A — `--save-renders` default-on** — grade CLI flag (opt-out `--no-save-renders`),
  `grade()` writes `rendered[page]` → `<out>/renders/<page>.png`, emit `test.sh`
  carries it, grade/emit tests updated. *(touches `grade/` + `emit/`)*
- **B — eval wrapper** — `eval/run_claude_code.py` + `scripts/evaluate.py`: pure
  argv-builder + clone-and-flip (tested), `subprocess` shell (untested). *(touches
  `eval/` + `scripts/`)*
- A and B are **independent (disjoint files) → buildable in parallel** (same rhythm
  as issues 21/22).
- *(then, HITL)* refresh 004's baked package → re-run 004 eval via the wrapper
  (`-k 10 -n 10`, `--force-build`) → faithful `verifier/renders/`.
- **C — report generator** — `eval/aggregate_results.py` (harvest → `scores.json`/
  `csv`) + `eval/failure_analysis.py` + `scripts/report.py` (plots + best/worst
  gallery → per-task `report.html`). Built against the fresh job.
- *(then, HITL)* run C across the analyzed task(s) → hand-write
  `reports/model-eval/README.md` from the real drill-downs.
- Also fold the **generation concurrency bump** (`modal_batch.DEFAULT_CONCURRENCY`
  8 → 10) in with A or B.

## Report generator (C) — locked v1 contents (2026-05-31)

The automated per-task `report.html` is a **self-contained evidence dashboard for
one eval job** — everything computable from `jobs/<name>/`, no narration. The
hand-written `README.md` selects from it. **v1 scope: items 1–7 only** (Meta +
Scores & distributions + Visual evidence); diagnostics, footer, and the optional
extras are explicitly **deferred** (listed at the end).

**Meta**
1. **Provenance header** — task id, seed tuple (archetype/aesthetic/complexity),
   model, agent, executor, n trials, total cost + tokens, wall-clock, date, repo
   commit. *(`result.json` + task `seed.json`)*

**Scores & distributions**
2. **Score table** — per-trial `reward` + 4 terms + a summary row
   (median / mean ± std / min / max); sortable. *(per-trial `reward.json`)*
3. **Reward distribution** — box/strip of the rewards + four per-term box plots.
4. **Per-term mean bars (± std)** — the skill-shape at a glance.
5. **Per-page × per-term heatmap** — mean across trials; localizes weakness.
   *(`reward-details.json` → `pages`)*

**Visual evidence** *(from `verifier/renders/` + reference PNGs)*
6. **Per-metric best/worst gallery** — for **each of the 4 metrics**:
   `reference | best page-render | worst page-render`, score-labeled + a score-range
   annotation (so the near-identical low-variance pairs, e.g. color, read as
   "uniformly good", not "no signal"). Extremes taken at the (trial, page) level.
7. **Best-overall attempt vs reference, all pages** — the highest-`reward` trial
   across every page: the "how close can Opus get" ceiling visual.

**Sidecar (the harvest contract, not a report section):** normalized
`scores.json` + `scores.csv` written alongside `report.html` (per decision #3).

**Deferred (not in v1):** page-presence/completeness table; inter-term correlation
matrix; caveats footer; the auto text word-diff; the `--oracle-job` distribution
overlay. Revisit after the first real 004 report exists.

**Automated/manual boundary (unchanged):** the dashboard answers "what happened in
this job" deterministically; the README answers "what it means" — validity backbone
(perturbation ladder + oracle-vs-Opus gap + cross-method agreement), the curated
killer example, cross-task synthesis, limitations/taste/decision-trail/dataset
showcase.

## Still open

- **Scope** — single task (004) deep-dive first; opportunistic 10-task × 10
  benchmark grid as the "behaviors across the distribution" stretch (decide after
  the 004 report exists).
