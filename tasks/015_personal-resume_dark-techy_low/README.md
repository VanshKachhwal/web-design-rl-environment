# 015_personal-resume_dark-techy_low

**Seed tuple:** `['personal-resume', 'dark-techy', 'low', 'health-and-wellness-seekers', 'nostalgic-and-charming']`
**Archetype / Aesthetic / Complexity:** personal-resume · dark-techy · low (5 pages)

## Eval results — Claude Code + Opus 4.7, 10× attempts

| reward (median) | mean ± std | min | max |
|---|---|---|---|
| **0.798** | 0.797 ± 0.003 | 0.792 | 0.801 |

Per-term means: structure **0.768** · color **0.963** · content **0.712** · design_judge **0.745**
(weakest term: **content**)

Open [`report.md`](./report.md) for the full visual report (score table, distributions,
per-page × per-term heatmap, and reference-vs-candidate galleries). Raw numbers in
[`scores.json`](./scores.json) / [`scores.csv`](./scores.csv).

## Narrative

**The design.** A personal résumé / portfolio site for a freelance product designer-developer.
The aesthetic is dark-techy: a near-black / deep-navy background, a bright teal-cyan neon accent
(with a warm amber secondary), geometric sans-serif type, modular card grids, and subtle glow on
the CTAs. Five pages (index, projects, experience, about, contact).

**Why higher reward = better replication — and why this task is so consistent.** This bundle has
the **tightest reward spread in the entire set: 0.797 ± 0.003.** That low variance is itself the
finding — the page is structurally simple (repeating modular cards, a single linear vertical
flow), the palette is distinctive and trivial to apply (teal-on-black), and there are few type
sizes to get wrong. There is very little for ten independent attempts to diverge on, so they all
land in the same place. The best-index attempt is ~95% faithful — even the headline colour-split
(one word in teal) is reproduced ([best-index candidate vs reference](./images/best_index_cand.png)).
This task is the "high-confidence, low-noise" datapoint: when the design is tractable, the grader
returns a tight, repeatable reward.

**What the model struggled with.** `content` is the weakest term (0.712). On the experience page
([worst-content candidate vs reference](./images/worst_content_cand.png)) the résumé text — job
titles, company names, dates, the bio, even the headline stats (8+ becomes 18+) — is *invented*
rather than transcribed. This is the hard ceiling of the whole environment in miniature: the agent
is given only screenshots, so dense biographical prose gets confabulated into plausible-but-wrong
copy. Structure and the judge stay solid, so within the (small) spread `content` is what
separates the trials.
