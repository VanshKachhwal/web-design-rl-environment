# Task 2 — Animations (a time-boxed attempt)

Part 2 of the brief: *"add animations. Judge the model's ability to perfectly
replicate these animations."*

> **This is a deliberately time-boxed attempt, and it shows.** Part 1 is the focus
> and the polished deliverable; Part 2 was built in the time left over, so the
> **research is incomplete and the code here is rougher than `src/webdesign_rl`** —
> more duplication, lighter test coverage, fewer iterations, and at least one known
> metric limitation analysed but not yet fixed (the 6-frame filmstrip, below). What
> follows is the reasoning we *did* get to — owned, with the gaps called out plainly.
> Part 2 is **not** part of the final [`tasks/`](../tasks/) deliverable; preliminary
> animation tasks + reports will land under `task2/tasks/`.

It has two halves, both end-to-end and runnable:

1. **A single-task validity proof** — one rich animated site, an eval-ready Harbor
   task, and a 3-term animation grader, with a perturbation ladder proving
   *higher reward = better animation replication*.
2. **A scaling pipeline** — generate diverse animated sites on Modal → lean gate →
   curate → grade with Claude Code + Opus 4.7 → report, mirroring Task 1's recipe
   with the fundamental **static → animated** changes (a new filmstrip render, a new
   reward, a two-pass generator, a lean gate).

The agent is shown a **timed filmstrip** — full-page frames captured at fixed times —
**not a video**. The brief permits passing video recordings; we chose deterministic
timed frames because they are *seekable and byte-reproducible* (see determinism
below), which a screen recording is not — and a reproducible reference is the whole
basis of a trustworthy reward.

> **Isolation.** Everything here lives under `task2/`. The Task 1 grader/generator/
> render/eval (`src/webdesign_rl`, `scripts/`, `tasks/`) is **never modified** — the
> animation grader *imports* Task 1's static metrics and judge read-only and reuses
> them unchanged. The duplication (render plumbing, the harvester + report) is
> deliberate: it keeps Task 1 frozen, and the grader + generator approach changed
> enough (static → animated) that sharing code would have coupled the two.

## The decisions

*Core design decisions for the animation environment. The "reference site" and
"scope" rows describe the single-task validity proof; the scaling pipeline (further
down) generates many multi-page sites instead.*

| Decision | Choice | Why |
|---|---|---|
| Reference site | **single focused generation** | one API call → one rich, human-looking animated landing page (true to the recipe ethos, fast) |
| Determinism | **WAAPI timeline seek** | pause `document.getAnimations()` and set `currentTime` to fixed absolute times → byte-identical frames on any machine |
| Animation constraint | **CSS-only, timeline-seekable** | `@keyframes` + transitions are seekable; `requestAnimationFrame` JS is out of scope for v1 (not seekable) |
| Grade composition | **static\@final + motion + anim-judge** | richest signal, reuses Task 1 for the static third |
| Scope | **one rich animated landing page** | 3-4 motion types (entrance, stagger, infinite loop) on one page |

## How it works

**Filmstrip render (`render_anim.py`).** Task 1 freezes motion to get one still.
Task 2 needs frames *through* the animation, deterministically — so instead of
sleeping (timing drifts with CPU speed) we **seek the timeline**: pause every
animation and set its `currentTime` to fixed absolute offsets
(`0/200/500/900/1400/2000 ms`), then screenshot. Same `(page, t)` → identical
pixels, proven below. A "settled" frame (seek far past the end) gives the at-rest
design for the static terms.

**Reward (`grade_anim.py`).** Animation is ~2/3 of the score, fitting a Part-2 task:

```
page_reward   = mean(static_design, motion, animation_judge)
static_design = mean(structure, color, content, design_judge)   # Task 1 grader, on the settled frame
reward        = mean(page_reward over pages)                     # absent page -> 0
```

- **`static_design`** — Task 1's four terms, reused unchanged on the at-rest frame.
- **`motion`** (`motion.py`, deterministic) — the spatio-temporal motion *signature*:
  downsample each frame to a coarse luminance grid, diff consecutive frames →
  a `(K-1, rows, cols)` tensor of *where/when/how-much* things move. Compare ref vs
  candidate by **pattern** (cosine of the flattened tensors) × **magnitude** (energy
  ratio). A static candidate → ~0; a perfect one → 1.0.
- **`animation_judge`** (`anim_judge.py`, VLM) — Sonnet rates the two filmstrip
  *contact sheets* on `motion_presence / timing / easing_feel / motion_type`.

`--no-judge` drops both VLM terms for fully-deterministic, free, offline grading.

## Does higher reward mean better animation replication? (the proof)

`perturb_anim.py` derives controlled variants from the reference — every variant
still **settles to the same design**, so only the *animation* changes — and grades
them deterministically:

| variant | what's wrong | reward | static_design | motion |
|---|---|---:|---:|---:|
| `oracle` | nothing (perfect) | **1.000** | 1.000 | 1.000 |
| `slow` | every animation 8s → entrance only partly plays in-window | 0.608 | 0.993 | 0.223 |
| `static` | durations ~0 → looks settled, never moves | 0.543 | 0.991 | 0.094 |
| `delayed` | every animation delayed 4s → motion after the window | 0.496 | 0.992 | 0.000 |

Reward falls **monotonically** with motion correctness; the oracle is the ceiling;
**partial motion beats none** (`slow` > `static`,`delayed`); and `static_design`
stays ~0.99 throughout — so the **~0.50 reward drop is isolated to the animation
terms**, not the design. That is the honest "higher reward = better animation"
signal, the same shape as Task 1's perturbation ladder.

**Full-mode (live judges) sanity check** — oracle vs the no-motion candidate:

| candidate | reward | static_design | motion | animation_judge |
|---|---:|---:|---:|---:|
| oracle (identical) | **0.925** | 1.000 | 1.000 | 0.775 |
| static (no motion) | **0.573** | 0.975 | 0.094 | 0.650 |

The reward discriminates strongly. Note the deterministic `motion` term carries it
(1.0 → 0.09); the VLM `animation_judge` is the *soft* signal (it scores even the
identical oracle only 0.775 — the same VLM conservatism that gives Task 1's design
judge ~0.76 on an oracle, and it struggles to tell a no-motion page from a settled
one on a static contact sheet). **Design intent: `motion` is the reliable anchor,
the judge adds feel.**

## The `motion` term, in detail

`motion` (`motion.py`) is the deterministic backbone — no model call, no randomness.
It asks: *does the candidate's animation move like the reference's — in the same
places, at the same times, by the same amount?* Construction:

1. **Signature.** Downsample every filmstrip frame to a coarse **16×12 luminance
   grid** (~192 cells — fine enough to localise hero vs cards vs footer, coarse
   enough that exact text/pixels don't dominate), then take the absolute difference
   between *consecutive* frames. That yields a `(K−1, 12, 16)` tensor of per-cell
   change-over-time — *where* on the page motion happens, *when* across the strip,
   and *how much*.
2. **pattern** = cosine similarity of the two flattened tensors (reference vs
   candidate). Scale-free; rewards motion happening in the *same regions at the same
   times*.
3. **magnitude** = `min(energy_ref, energy_cand) / max(…)`, where energy is total
   summed change. Penalises a candidate that moves *far too little* (a static page →
   ~0) or *far too much*.
4. **`motion = pattern × magnitude`** ∈ [0, 1]. Identical → 1.0; static → ~0; both
   filmstrips equally still → 1.0 (a faithful "nothing moves" match, not punished).

Because both filmstrips are seeked to the *same absolute times*, a candidate with the
wrong duration/easing renders different pixels at each `t` and is penalised
automatically — no per-element transform parsing needed.

## The fixed 6-frame filmstrip — the main known limitation

Every page is sampled at a **fixed 6 timestamps**, the same for every task:

```python
DEFAULT_TIMESTAMPS_MS = (0, 200, 500, 900, 1400, 2000)   # render_anim.py
```

This is **not proportional to the animation's length** — a 600ms entrance and a 6s
loop are both sampled at these same 6 points. For *our* generated dataset that is
mostly fine: the generator steers toward entrances/staggers that play within ~2s, so
the window brackets the motion (and the perturbation ladder above confirms the term
is monotonic on those sites). But it has a real, analysed failure mode:

> When a reference animation is **very fast**, almost all of its motion energy lands
> in a single temporal bucket. We measured this on a real eval: the reference's hero
> entrance was essentially complete by 200ms (energy `[9.3, 3.1, 0.4, 0, 0]` across
> the 5 inter-frame transitions), while Claude built a slightly slower, more
> staggered entrance peaking one bucket later (`[0.2, 7.8, 3.5, 0.3, 0]`). Because
> the signature is consecutive-frame diffs, a **one-bucket shift makes the temporal
> vectors near-orthogonal**, so the cosine — and `motion` — collapses (~0.16) for a
> difference that is visually a near-miss. `magnitude` and the *spatial* cosine both
> stayed ~0.95; the entire loss was temporal.

So the score is **strict in a way that exaggerates small timing offsets** for
fast animations. It is honest (the candidate genuinely mistimed the entrance) but
harsher than a human eye. The fix directions — denser/log-spaced early sampling, a
cumulative (vs consecutive-diff) signature, or sampling proportional to the observed
animation length — are scoped but not built; this is the first thing Part 2 needs.

## What the model struggled with (early eval observations)

Evals are still running, so these are **preliminary** (one well-analysed task plus
the single-task proof), but two patterns are already clear and consistent with Part 1:

- **Claude builds shorter pages.** On the 5-page saas eval, every candidate page was
  **~0.55–0.62× the reference's height** — the model reproduces the sections and look
  but compresses vertical rhythm and omits the longer filler stretches (the same
  *structure*/vertical-rhythm gap Part 1 surfaces, now visible page-by-page).
- **Claude animates to its own taste, not the reference's timing.** The prompt
  discloses *when* the frames are sampled but not the underlying durations/easing, and
  the model defaults to conventional ~400–900ms staggered entrances rather than
  matching the reference's faster ones — which the strict `motion` term then penalises
  (amplified by the 6-frame limitation above).

## The reference site

`reference/aurora/index.html` — *Aurora*, a sleep & focus app landing page (dark
indigo→teal, geometric sans), a single self-contained file with **23 CSS
animations**: a hero fade/slide entrance, staggered feature-card reveals, and
infinite loops (pulsing accents, gradient shifts). See
`reference/aurora_filmstrip/contact.png` (the motion over time) and `settled.png`
(the at-rest design).

## Honest limitations

- **The fixed 6-frame filmstrip** is the biggest one — strict about small timing
  offsets for fast animations and not proportional to animation length (analysed in
  full above). Scoped fixes exist; none is built yet.
- **Rougher code than Part 1.** Time-boxed: more duplication, lighter test coverage
  (the deterministic cores are unit-tested; the LLM / Playwright / Modal / Harbor
  shells are not), and the single-task `aurora` proof predates the scaling pipeline.
- **CSS-only / timeline-seekable.** JS/`rAF`, scroll-triggered, and hover-triggered
  animations are out of scope — seeking the timeline only covers declarative
  animations. The generation prompt enforces it; the lean gate rejects `<script>`.
- **Filmstrips, not video** — a deliberate determinism choice (above), but smooth
  sub-frame motion *between* samples is invisible to the grader.
- **The VLM animation judge is soft** (see above) — it scores even the identical
  oracle ~0.78; `motion` is the reliable anchor and the judge only adds feel. A
  stronger version would feed an interleaved frame sequence or per-element transform
  traces, not a contact sheet.
- **Agent-facing frames are host-rendered** at emit time (Task 1 later moved its
  agent screenshots in-container to kill font drift; not redone here). Grading is
  unaffected — the verifier renders ref *and* candidate in the same container.

## How to run (single task)

In short: `generate_anim` → `perturb_anim` (free proof) → `emit_anim` → flip the
agent env online → `harbor run -a claude-code -m claude-opus-4-7`. The reward lands
in `jobs/<name>/.../verifier/reward.json` with the full breakdown in
`reward-details.json` and the graded frames in `renders/`. Build the evidence
dashboard for any saved job with `python -m webdesign_rl_anim.report_anim
jobs/<name>` (see the report's five sections under *Scaling* below).

---

## Scaling: a diverse animated dataset (Modal)

Mirrors Task 1's scalable pipeline — generate on Modal, curate, grade on Modal,
report — but **two-pass and lean** for throughput. All knobs are configurable.

**Generation is two LLM passes, no structural enforcement** (we trust the LLM):
- **Pass 1** (`two_pass.run_plan`): one call decides the brief + a free-form 5-page
  sitemap and authors the shared `styles.css` + `animations.css` + header/footer.
- **Pass 2** (`two_pass.run_build`): one call builds every page body against that
  shared system, applying the animation utility classes so each page animates.

**Diversity** comes from *soft seeds* (`seeds_anim`): Task 1's deterministic
`archetype × aesthetic` grid-walk plus an **animation-style** axis (smooth-fade /
snappy-slide / playful-bounce / elegant-reveal / kinetic-loop), threaded into Pass 1
as creative direction — **steers, not constraints** (no component catalog/manifest).

**Lean gate** (`gate_anim_lean`, render-based): a site passes iff every page (1) is
present + shared CSS exists, (2) has no `<script>`, and (3) renders non-blank with
`n_animations > 0` and frames that actually vary over time. Everything else from
Task 1's gate (substance/token/manifest/chrome/font) is dropped for throughput.

This is a **deliberate throughput-over-strictness trade**, and it shows in the yield:
Task 1's stricter multi-check gate rejects a fair fraction of rollouts (so we
over-generate heavily there), whereas the lean gate passed **19 of 20** generation
rollouts on the committed batch — **95% yield** (the one drop, `018`, failed the
renders/animates check and was left with only its `site/`). High throughput is partly
a *feature* of trusting the LLM (two-pass, no structural enforcement) and partly a
*caveat*: the lean bar lets through sites Task 1's gate would have caught, so quality
control leans more on the eval + curation than on the gate.

```bash
export $(grep -v '^#' .env | xargs)        # ANTHROPIC_API_KEY (for local steps)

# 1. GENERATE on Modal: over-generate stratified animated 5-page sites, gate, emit
#    survivors as Harbor tasks, write to a Modal volume. (HITL: needs Modal auth +
#    the `anthropic-api-key` Secret provisioned.) The committed batch used --count 20
#    (19 survived the lean gate). Configurable.
PYTHONPATH=task2:src .venv/bin/python -m webdesign_rl_anim.modal_batch_anim \
  --count 20 --concurrency 10 --volume webdesign-rl-anim-artifacts

# 2. PULL the batch down locally (reuses Task 1's volume puller, read-only).
PYTHONPATH=src .venv/bin/python scripts/pull_artifacts.py \
  --volume webdesign-rl-anim-artifacts --out task2/out/anim-batch

# 3. CURATE: keep one survivor per (archetype, aesthetic) cell -> ~10 diverse tasks.
PYTHONPATH=task2:src .venv/bin/python -m webdesign_rl_anim.curate_anim \
  --batch task2/out/anim-batch --out task2/out/anim-curated --limit 10

# 4. GRADE at scale (eval-all): Claude Code + Opus 4.7, 10x per task, on Modal,
#    a couple tasks in parallel. Clones each task, REFRESHES both baked grader
#    packages to current code, flips the AGENT env online, reuses Task 1's argv.
PYTHONPATH=task2:src .venv/bin/python -m webdesign_rl_anim.evaluate_anim \
  --tasks task2/out/anim-curated --executor modal \
  --attempts 10 --concurrency 10 --parallel 2 --yes
# rewards land in jobs/anim-<id>/.../verifier/reward.json (+ reward-details, renders)

# 5. REPORT: harvest each eval job into a per-task evidence dashboard. Decoupled
#    from eval and freely re-runnable (no grading). Sweep every job, or one job.
#    Task-1 STATIC jobs in the same jobs/ dir are auto-skipped (animation jobs
#    are detected by their filmstrip-graded reward-details).
PYTHONPATH=task2 .venv/bin/python -m webdesign_rl_anim.report_all_anim jobs/ \
  --out-root task2/reports --format markdown
# or a single job:  python -m webdesign_rl_anim.report_anim jobs/anim-<id>
```

**The report** (`report_anim` / `report_all_anim`) mirrors Task 1's but keeps only
the **five data sections** — no embedded screenshot/filmstrip galleries (for
animations those would be 6 frames × ref/cand × every page × every trial). Each
job writes `scores.json` + `scores.csv` (the harvest contract) plus a
self-contained `report.html` (or GitHub-renderable `report.md` + PNGs):

1. **Provenance** — task id, seed tuple, animation style, model, executor, trials,
   cost/tokens, wall-clock, filmstrip timestamps, date, commit.
2. **Per-trial scores** — `reward` + the three animation terms, with a
   median / mean ± std / min-max summary row.
3. **Reward + per-term distributions** (box + strip).
4. **Per-term mean bars** (± std) — the animation skill shape.
5. **Per-page × per-term heatmap** (mean across trials).

Terms are the animation page-reward terms **`static_design` / `motion` /
`animation_judge`** (`reward = mean` of the three, per page, averaged over pages);
the four static sub-terms stay nested under each page in `scores.json` for
drill-down.

Modal config knobs: `--count` (over-generate size), `--concurrency` (`max_containers`),
`--volume` (artifact volume). Grading: `--executor docker|modal`, `--attempts/-k`,
`--concurrency/-n`. The generation Modal app is `webdesign-rl-anim-batch` (its own
app/volume, distinct from Task 1's so they never collide); the sealed image is Task
1's render image **plus** this package on PYTHONPATH, so generation, the gate's
filmstrip render, and emit all run in the exact grade-time image.

> Isolation holds at scale too: the only Task-1 touch is **read-only imports**
> (`sample_seeds`, `normalize_stage3_body`, the render image Dockerfile, `_copy_package`,
> `build_harbor_argv`). Verified: `git diff src/ scripts/ tests/` is empty.
