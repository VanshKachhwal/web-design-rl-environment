# 035_local-service_dark-techy_high

**Seed tuple:** `['local-service', 'dark-techy', 'high', 'local-community', 'premium-and-understated']`
**Archetype / Aesthetic / Complexity:** local-service · dark-techy · high (10 pages) *(clean run; folder renamed from job `opus47-035`)*

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.739** | 0.736 ± 0.012 | 0.716 | 0.752 |

Per-term means: structure **0.738** · color **0.977** · content **0.544** · design_judge **0.685**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** *NexCore Cleaning Services* — a premium local-service (commercial cleaning)
business. The aesthetic is dark-techy at high complexity: a charcoal background, an electric
cyan accent with magenta secondary, uppercase headings with cyan inline keywords, clean line
icons, analytics-style stat blocks, and accordion sections. Ten pages (index, services, pricing,
about, contact, areas, gallery, reviews, booking, faq).

**Why higher reward = better replication.** `color` is near-ceiling (0.977) and `structure`
is solid (0.738), so the reward (0.716 → 0.752) is governed by `content` — and this task has the
**lowest `content` score in the entire set: 0.544.** That makes it the sharpest illustration of
the headline behaviour: across a 10-page, text-heavy site, the agent reliably template-replicates
*structure* while genericising the *copy*. The best trial (`KbwY6JH`, 0.752; [`report.md`](./report.md)
§7) keeps the hero, the service grid, the stat block and the testimonial cards close — and even
it cannot rescue the content term. Reward tracks copy fidelity, which is precisely the dimension
that degrades most here.

**What the model struggled with.** The FAQ page is the worst content page (one trial scores
**0.326**, [candidate vs reference](./images/worst_content_cand.png)): the reference's dense,
multi-sentence Q&A answers are hollowed to one-line fragments — there is nowhere to hide on a
page that is almost pure text. Structure also has a worst page on reviews ([candidate vs
reference](./images/worst_structure_cand.png)) where the testimonial-card grid loses uniformity:
spacing and padding drift between cards and the star rows fall off-register. The overall lesson
this bundle teaches is the cleanest in the set — *layout is cheap to copy from a screenshot; dense
prose is not*, and the `content` term is what makes that visible in the reward.
