# Task 2 — Animations (one honest attempt)

Part 2 of the brief: *"add animations. Judge the model's ability to perfectly
replicate these animations."* This is a deliberately **non-scale** attempt — one
good animated website, an eval-ready Harbor task, and a grader extended to score
animation replication — built in the final hours without touching any Task 1 code.

> **Isolation.** Everything here lives under `task2/`. The Task 1 grader/generator/
> render/eval (`src/webdesign_rl`, `scripts/`, `tasks/`) is **never modified** — the
> animation grader *imports* Task 1's static metrics and judge read-only and reuses
> them unchanged. Duplication (the local server / network-block render plumbing) is
> intentional, to keep Task 1 frozen.

## The decisions

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

## The reference site

`reference/aurora/index.html` — *Aurora*, a sleep & focus app landing page (dark
indigo→teal, geometric sans), a single self-contained file with **23 CSS
animations**: a hero fade/slide entrance, staggered feature-card reveals, and
infinite loops (pulsing accents, gradient shifts). See
`reference/aurora_filmstrip/contact.png` (the motion over time) and `settled.png`
(the at-rest design).

## Honest limitations (v1, ~one evening)

- **One page, one site.** Not at scale — a recipe, proven on a single task.
- **CSS-only.** JS/`rAF` motion, scroll-triggered, and hover-triggered animations
  are out of scope (the seek-the-timeline trick covers declarative timeline
  animations). The generation prompt enforces the constraint.
- **The VLM animation judge is soft** (see above). A stronger version would feed an
  interleaved frame sequence or per-element transform traces, not a contact sheet.
- **Agent-facing frames are host-rendered** at emit time (Task 1 later moved its
  agent screenshots in-container to kill font drift; not redone here). Grading is
  unaffected — the verifier renders ref *and* candidate in the same container.

## How to run

See the command block in the repo chat / below. In short: `generate_anim` →
`perturb_anim` (free proof) → `emit_anim` → flip the agent env online →
`harbor run -a claude-code -m claude-opus-4-7`. The reward lands in
`jobs/<name>/.../verifier/reward.json` with the full breakdown in
`reward-details.json` and the graded frames in `renders/`.
