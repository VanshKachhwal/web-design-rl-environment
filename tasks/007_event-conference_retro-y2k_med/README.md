# 007_event-conference_retro-y2k_med

**Seed tuple:** `['event-conference', 'retro-y2k', 'med', 'health-and-wellness-seekers', 'nostalgic-and-charming']`
**Archetype / Aesthetic / Complexity:** event-conference · retro-y2k · med (7 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.727** | 0.735 ± 0.035 | 0.703 | 0.836 |

Per-term means: structure **0.759** · color **0.941** · content **0.6** · design_judge **0.639**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *WellnessCon 2025* — a health-and-wellness conference site. The aesthetic is
retro-y2k: purple-to-magenta gradient backgrounds, hot-pink and acid-lime buttons, glowing/haloed
headline text, beveled button shapes, hard saturated colour-blocking, and circular avatar photos.
Seven pages. This is deliberately the hardest aesthetic in the set — it asks for *intentional*
early-2000s excess.

**Why higher reward = better replication.** This task has the lowest `design_judge` (0.639) and
the lowest `content` (0.60) of the whole set, and the widest reward spread (0.703 → 0.836) — which
is itself informative: the grader is *discriminating* strongly here. `color` (0.941) is the
**lowest color score in the whole set** — the saturated purple-to-magenta gradients and the neon
pink/lime are the single hardest palette here to match exactly — yet it is *still* this task's
strongest term by a wide margin, so even at the set's worst, color is not the limiter. The spread
is driven by whether an attempt actually *feels* y2k. The best trial (`ktrPUUd`, 0.836; [`report.md`](./report.md) §7) keeps the gradients,
colour-blocking and beveled buttons; lower trials sand the era off into clean modern SaaS. Reward
tracks "how y2k did it stay".

**What the model struggled with.** The speakers page is the worst page for both weak terms. For
`design_judge` (worst 0.500, [candidate vs reference](./images/worst_design_judge_cand.png)) the
retro warmth is stripped: solid hot-pink avatars flatten, the beige description cards turn plain
white, the glow/bevel depth disappears, and the page reads like a tasteful contemporary template —
the model's prior pulls it toward "clean" when the brief demands "loud". For `content` (worst
**0.363**, [candidate vs reference](./images/worst_content_cand.png)) the speaker bios are thinned
to short generic filler. The honest read: the model can match *layout and palette* of an
unfashionable style, but resists reproducing the deliberate maximalism — and the judge correctly
withholds reward for that.
