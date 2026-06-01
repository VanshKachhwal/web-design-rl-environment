# Thinking trail

This is my real-time working log, lightly cleaned up — the trail of how the decisions
in this project actually got made, in the order they happened. It keeps the dead-ends,
the bugs I hit, and the commands I was running at each point (they show what I was
trying to build at that moment, and how I tested it). The polished rationale lives in
[`design/`](./design/); this is the raw version.

It's phased roughly chronologically: grader first, then the generator, then evaluating
a real model, then packaging.

---

## Phase 1 — Framing the grader

I decided early to focus on **behavioral tests only** for this task. Writing exhaustive
coverage for a trial project didn't seem worth the hassle, though there's still real
utility in keeping behavioral tests.

**Should the grader see the generator's HTML + CSS?** No. The whole point is to test the
agent's ability to replicate a design from *visual information alone*. If I grade
against the source HTML/CSS, I'm leaking information the agent never had access to —
that creates a fundamental mismatch between what the agent sees and what it's graded on.

**What exactly is the reference?** The screenshots I pass to the agent. On page
mappings: I decided to pass screenshots already mapped (one per page) and instruct the
agent to build pages with matching names. That way the agent has an explicit instruction
in the Harbor pipeline and the grader already knows the mapping — deterministic. If the
grader had to figure out which file matches which screenshot, that's much harder and
injects noise into grading.

**Viewport.** I'll restrict viewport width and state it in the instruction markdown, so
the agent isn't penalized for something it was never told. (I wasn't completely sure
this was right at the time, but it's the defensible default.)

I also wanted to crunch some assumptions for the *second* task up front while building,
so the grader could be designed accordingly.

---

## Phase 2 — Choosing the metrics

Research on what to build the grader on, and which to actually use:

1. **OCR text match** — looks non-gameable.
2. **MS-SSIM** — detects position of text blocks; also very cheap.
3. **Color — CIEDE2000** — for color difference.
4. **Structure** — block-match area, to detect hallucinations.
5. **LPIPS/DISTS** — nice in principle (pretrains a CNN for comparison), but probably
   out of scope for the current state.
6. **Design judge** — a VLM rubric.

These are among the metrics used inside the Design2Code benchmark, which gave me
confidence to rely on them.

To set the **weights**, I figured I could run a monotonicity study to find the right
proportions. For now I kept the weights **equally distributed** instead of tuning them
from the study — if time permits I can adjust and re-verify. To grade multiple pages
into one score, I take the **mean across pages** — the easiest defensible default (the
monotonicity study can validate the grader is sound on all parts).

---

## Phase 3 — Render, and the first validation

For rendering I use **Playwright + Chromium** to take a headless screenshot given a
directory of HTML/CSS files.

**Grader validation idea:** build a perturb-er that shifts a golden item along
different axes — layout, color, structure. The grader should detect the changes; and as
I increase the *severity* of the perturbations, the reward curve should show a
**monotonic decrease**.

**Result of the initial validation:** the different metrics are working correctly.
But I noticed the **color grader is fairly forgiving**, along with structure, for cases
where the output is mostly a white background. I figured I could validate on tougher
examples to see its real power — but before that, I wanted to build a complete product
so I could run these validations on Modal too.

> The worst assumption I feel we've taken so far is the assumption of bundled fonts.

### The validation curves (the payoff)

Once the full grader + perturbation harness was built, I ran the complete monotonicity
study (`scripts/validate_grader.py`, committed under `reports/grader-validation/`). The
whole point is to *prove* "higher reward = better replication" rather than assert it: I
manufacture variants of a hand-authored reference whose quality ordering is known a
priori, score them with the real grader, and check the reward respects that ordering.
Four curves, each answering a different question:

**1. Aggregate monotonicity — reward vs overall severity.** A combined source-space
ladder (palette shift + text deletion + element removal applied together, re-rendered)
degrades the whole site at once. The blended reward falls monotonically as severity
rises — `0.998 → 0.925 → 0.851 → 0.790 → 0.672 → 0.377` across severities `0.0 … 1.0`.
**Spearman ρ = −1.000**, pairwise-ordering accuracy **1.00**. This single curve is the
headline evidence for the central claim.

**2. Per-metric monotonicity — each term tracks its own axis.** I want each term to
respond to the thing it's *supposed* to measure, not ride on the others. It does:

- Image-space ladders all hit ρ = −1.000: `color_drift`→color; `gaussian_blur`,
  `spatial_shift`, `region_occlusion`, `pixel_noise`→structure.
- Source-space ladders: `delete_text`→content (−1.000), `shift_palette`→color
  (−1.000), `remove_element`→structure (−0.956).

**3. Ceiling and floor.** Oracle (the unperturbed reference) = **1.000** — the
ground-truth site scores at the top. Degenerate outputs that replicate nothing get
**floored** by the blend: `blank` 0.426, `solid_gray` 0.343, `lorem_ipsum` 0.433.

This is also where my earlier worry from the initial validation — *color/structure look
forgiving on white backgrounds* — gets resolved honestly rather than waved away. A
mean-gray fill sits ~ΔE 33 from both black and white, so the **`color` term alone is
generous** to a solid-gray page (~0.67). That's "reads palette, not mean," *not* a bug.
The anti-gaming guarantee lives on the **aggregate**: `content` (OCR finds no matching
text) and `design_judge` collapse to ~0, so the blended reward floors the degenerate far
below the oracle — no single lenient term can rescue a page that replicates nothing.

**4. Multi-page aggregation.** The reference is a 5-page site and the reward is the mean
over pages, so corrupting one page must drag the aggregate down. It does: all five
faithful = **1.000**; delete the text on one of the five = **0.908**. The per-page mean
propagates quality, as intended.

Taken together, these are what gave me confidence the reward is a real signal and not
noise: every axis monotonic, the oracle at the ceiling, the degenerates on the floor,
and a documented, *contained* lenient-term caveat instead of a hidden one. Every number
above is auditable in `reports/grader-validation/scores.json`.

---

## Phase 4 — The font gotcha (and the determinism principle)

> Before moving forward, I wanted to run the grader end-to-end through a Harbor workflow
> in a Docker environment, to be confident about progress. **Code without executable
> results doesn't feel worthy to me.**

That's where I hit it. There are **two separate moments** when HTML turns into pixels:

1. When the **reference** snapshot is created — in my case on the macOS host (my
   machine), and I committed those PNGs into the task.
2. When **grading** happens — inside the Harbor verifier container (Linux), the grader
   renders the candidate's HTML with the container's Chromium and compares it to that
   committed reference PNG.

These two renders happened in **different environments**, and then **font substitution**
bit me. On macOS, Arial exists → the host render used real Arial glyphs. In the Linux
container, Arial doesn't exist → Chromium silently substituted a fallback (DejaVu).
**SSIM dropped**, because text is high-frequency edge content. I fixed it by rendering
the reference **inside the same container** as the candidate at grade time.

This is what locked in the **"deterministic offline render with bundled fonts"**
decision. Why it matters specifically for *this* grader:

The grader compares pictures — a picture of the agent's site vs. a picture of the
target. If the *same* site produces a slightly different picture depending on which
machine rendered it (or how fast the network was that second), the score wobbles for
reasons that have nothing to do with design quality. The model learning from that reward
is chasing a moving target — learning noise. That's exactly the poison the brief warns
about. So I need a hard guarantee: same site code → exact same picture, every run, every
machine. Three things make rendering wobble, and the principle kills each:

- **Fonts → bundle them.** The biggest one (and the one that bit me). "Arial" means a
  different file (or a fallback) on different machines, which changes letter widths, line
  wraps, and everything below. Bundling the exact font files into the render environment
  makes "Arial" mean the same glyphs everywhere.
- **The internet → render offline.** Pages pull fonts/images/scripts from the network;
  anything fetched can be slow, fail, or change over time. Cutting the network during
  render means the page uses only what's packaged with it. **Bonus:** it also stops an
  agent from cheating by linking directly to the original site's assets — it forces a
  real recreation.
- **The browser/machine → pin it.** One headless Chromium, no GPU, fixed zoom, fixed
  1280px width, animations off. One sealed, identical kitchen.

Put together: one sealed, fully-stocked, internet-free rendering setup that turns any
site's code into the exact same picture every time, on any machine.

**Judge model.** Using **Sonnet as the judge while Opus 4.7 is the agent under test** is
a deliberate call to avoid self-preference bias.

---

## Phase 5 — Designing the generator

Options I went through for generation:

1. **Just give Claude a good prompt** and expect diverse, human-like sites. The risk I
   foresaw: repetitive outputs even with temperature tinkering. Need a good taxonomy.
2. **Two-stage generation** — a smaller model first generates a variety of themes/designs,
   then those feed into a code-trained LLM.
3. **Structured seed sampling** (from research) — achieve diversity by covering across
   application categories: `industry × layout_pattern × color_style × complexity_level ×
   page_count`, one website per combination.
4. **A quality gate** at the end.

Existing research claims say the **two-stage concept→code pipeline** is both simple and
scalable, so I went with simple methods to start.

**Image assets:** for the MVP, CSS only, no real images — the agent has no information
about external assets anyway, and avoiding them keeps tasks fully self-contained and
reproducible. Another framing I considered: create a **design spec** with one LLM, then
have a coding agent write the site UI from that spec.

Viewport width stays fixed.

After much thinking I settled on: a **3-stage generation pipeline plus a quality-gate
stage**. Fonts were the thing I knew I still needed to think hard about.

Early problems to fix in the generator:
1. The `max_tokens` issue when generating CSS/HTML.
2. Some gates (e.g. var-reference) are too strict — relax those.
3. Increase the number of model retries.
4. Figure out rate limits for generating 10+ tasks.
5. Add **logging between generator steps** — the pipeline felt hollow, just waiting for
   output with no command-line signal.

> I made these into issues and ran Claude to handle each of them.

I did wonder whether I could use **Claude Code in headless mode** with a good prompt for
generation too — since it's independent of grading, I could use both model and harness
to my advantage. (I came back to this question later; see Phase 9.)

---

## Phase 6 — Day 2: stabilize, scale, diversify

**Day 2 plan:**
- Get stable end-to-end runs; one manual run to eyeball quality.
- Investigate whether fixed-viewport-width screenshots are enough — would elongated
  screenshots work well for Claude in the pipeline?
- Generate **48 websites** via a Modal run with parallel compute, without breaking.
- Define a **diversity metric** to pick 10 of the 48.
- Nail down the grading pipeline so I can run **Opus 4.7 end-to-end** (expecting lots of
  tweaks).
- Push the ADRs, docs, and issues. Only move on to Task 2 once Task 1 is stable.

Initial generations looked good and fairly diverse, but I wanted more component variety
so they don't all look the same. Prioritized improvements (highest value first):

1. **Archetype-native components** — the single biggest lever. Per-archetype components
   (menu/dish-list, article-list for a blog, product-grid for ecommerce, hours,
   map/location). Fixes both fidelity (a real menu, not a pricing table) and structural
   diversity (each archetype stops looking like the same SaaS template).
2. **Break the layout-grammar repetition** — not every page needs a hero or a cta-banner;
   vary section ordering and which components appear. This is what makes sites feel
   *designed* rather than templated.
3. **Fix the "home is the sparsest" inversion** and raise per-page richness — home should
   be the densest; give it a higher section floor.
4. **Decide the imagery strategy** for visual archetypes — accept CSS-only as a known V1
   limitation (and lean curation toward archetypes where CSS-drawable reads well), or
   revisit shipping image assets post-V1.

Reality of the day:

> Working with different fonts is such a pain in the ass. Experiencing many failures here.

The **token-compliance** quality gate also felt too strict — particularly the px checks,
since the model occasionally puts random px values. I skipped relaxing it for now,
planning to run the Modal pipeline with 48 sites and read the failure rate there.

> It's 24 hours since I started, so I must wrap up the complete pipeline so it can be
> used and tested.

On parallelism: out of fear of rate limits, I **did not** make the stage pipeline async.
I'd test with serial calls for the pages inside stage 3 and stress-test later. A single
site takes ~8 minutes. To dodge rate limits I just launch **8 Modal workers in
parallel** making the API calls — enough given ~8 min/site; ~50 sites should finish in
about an hour. The grader takes ~6 minutes per task.

The taxonomy only has 10 aesthetics and 10 archetypes — I want to expand for more
diversity, but skipped it for now.

> I think I could have gone with Claude Code as the generator; that would've made things
> so simple since all the harness and error handling is already built. If time permits,
> maybe I'll try it.

And a realization that shaped the eval design: I first thought I'd evaluate **Opus 4.7**
on the tasks, but since I'm evaluating **Claude Code**, the agent needs internet access
(it makes Anthropic API calls to think) — which is why the eval flips `allow_internet`
on for the agent only (see Phase 8).

**The 50-site batch result:**

```
batch: 38/50 passed (yield 76.0%); 12 dropped, 0 errored
drops by check: stage-2-inline=12
nudges by check: token_compliance=37, substance_height=4, catastrophic_layout=1
components used: hero=38, cta-banner=38, form-field=38, content-section=38,
  header=38, footer=38, contact-block=38, feature-grid=37, newsletter-signup=36,
  testimonial=35, stat=34, map-embed-placeholder=33, split-screen=33, faq=33,
  timeline=31, bento-grid=30, award-badge=27, card=25, filter-bar=25,
  comparison-table=23, logo-cloud=23, team-card=21, step-process=20,
  pricing-table=20, badge=18, masonry-grid=16, gallery=16, sidebar-layout=13,
  blog-post-card=10, speaker-card=9, button=8, code-snippet=8,
  metric-dashboard=6, menu-card=5, icon=4, product-card=3, link=3, job-listing=3
```

76% yield, all drops from one check (`stage-2-inline`), zero hard errors — a healthy
signal that the pipeline is stable and the gate is doing real work.

---

## Phase 7 — Running Opus 4.7 ten times (the eval)

First I needed one real 10× job on disk. The steps and commands I worked out for the
`004` task:

**Step 1 — Environment.** Both keys must be present: the agent key (Opus writes code)
and the verifier key (Sonnet judges).

```bash
cd /Users/vansh/Code/open_source/web-design-rl-environment
set -a; source .env; set +a
echo "key length: ${#ANTHROPIC_API_KEY}"     # expect non-zero
modal profile current
```

**Step 2 — Give the agent env internet.** The `task.toml` sets `[environment]
allow_internet = false` (deliberate: the rendered site must be hermetic). But the
claude-code agent runs inside that env and must reach `api.anthropic.com` to think. So
for the eval I flip the agent env on (verifier stays as-is), on a **throwaway eval
copy** so the canonical offline fixture stays untouched:

```bash
mkdir -p out/eval
cp -r out/curated/004_local-service_luxury-serif_med out/eval/004
sed -i '' 's/^allow_internet = false/allow_internet = true/' out/eval/004/task/task.toml
grep -n allow_internet out/eval/004/task/task.toml   # [environment] now true; verifier already true
```

This doesn't weaken well-posedness — hermeticity is enforced at *grade time* by the
offline verifier + the static-only gate, not by starving the agent of network while it
authors. (The sites are CSS-drawable-only, so there's nothing external to fetch anyway.)

**Step 3 — Run 10 attempts on Modal.**

```bash
~/.local/bin/harbor run \
  -p ./out/eval/004/task \
  -a claude-code -m claude-opus-4-7 \
  -e modal --force-build \
  -k 10 -n 5 \
  --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --artifact /logs/artifacts \
  --job-name opus47-004
```

`-k 10` = the brief's ten attempts; `-n 5` = five concurrent on Modal; `--ae` hands the
agent its key; `--artifact` pulls each attempt's produced HTML back into `jobs/…`.

**Step 4 — Read the results.**

```bash
~/.local/bin/harbor view
JOB=$(ls -dt jobs/opus47-004* | head -1)
.venv/bin/python -m json.tool "$JOB/result.json" | grep -A40 '"metrics"'
```

It takes around **26 minutes** for Claude Code to run 10× on a task with 5 workers
(later, at `-n 10`, the `004` job ran ~$2/trial, ~13 min/trial, ~$20 / 27 min total).

**On a consolidated score.** After 10× scoring, I report **median + mean ± std +
min/max**, not a lone number:
- Median is the headline figure — robust if one attempt crashes to 0.
- Mean ± std shows central tendency and reliability (std = reward noise, which matters
  for RL).
- Per-term means (structure/color/content/design_judge) show the *shape* of the skill.

Am I *required* to give a single scalar? No — the brief asks "running Opus 4.7 10
times… how well does the grader score the results?" That's about the **distribution and
the grader's validity**, not a mandated number. Reporting only a mean would be worse
than showing the spread. For this single-task deliverable, three things matter: (1) the
score distribution across the 10 runs, (2) the validity argument (why higher score =
better replication — best shown by a ranked screenshot gallery beside the reference),
and (3) the failure patterns.

My sequencing rule held throughout: **run the real 10× job first, then build the report
harness against that actual data** — same "validate against real artifacts, don't design
in the abstract" discipline, rather than writing plotting code blind and getting
surprised by the JSON shape or a failed rollout.

---

## Phase 8 — The big learning: content is paraphrase, not transcription

After just one eval I could already see: **Claude performs really well on color and
structure, and not as well on content.** Digging into the low content score, it's
**correct** — it's heavy paraphrase + omission, not an OCR glitch.

Why the model does this, ranked by likely contribution:

1. **It's given pixels, not text — and generation is its native mode, not
   transcription.** Faced with reading every word off a screenshot, an LLM defaults to
   producing fluent, plausible marketing copy that "sounds right" for an about page,
   rather than laboriously transcribing verbatim. It reconstructs meaning, then
   re-writes — which is exactly paraphrase.
2. **Visual-salience bias.** Large, high-contrast elements (headings, nav, big stat
   numbers) get copied accurately; small, dense, low-contrast paragraph text gets
   approximated. This explains the per-page curve: pricing/index (short labels, big
   numbers) score 0.75–0.82; about/gallery/services (dense prose) score 0.40–0.47. Same
   effect *within* a page — headings match, paragraphs don't.
3. **Semantic-substitution drift.** Swappable specifics get plausible replacements
   ("Satisfaction"↔"Retention", "two decades"↔"a decade") — the signature of
   reconstructing from memory.
4. **Length/effort truncation.** Shorter copy, whole blocks omitted (team bios).
   Transcribing 800 words is tedious; the model satisfices.
5. **The framing nudges it toward "look," not "text."** The instruction says *replicate
   the design*; the agent reasonably reads that as layout/color/typography-first and
   treats exact wording as secondary. Its behavior is almost rational given the framing.
6. **Inherent lossiness of the channel.** A screenshot is a lossy encoding of 800 words.
   Even a careful human would paraphrase. Some content loss is baked into a
   screenshot-only task.

Two honest caveats:

- The metric is **OCR word-multiset F1 on the rendered screenshots**, not on the HTML.
  A quick HTML-text proxy gave F1≈0.59 for this trial vs. the measured ~0.45 — the gap
  is partly OCR (dense paragraph text is harder to recover than the proxy assumes) and
  partly that the proxy counts perfectly-matching nav/headings as full tokens. The
  *direction* is robust; the exact number carries some OCR noise.
- This raises a genuine **design-taste question**: is verbatim text the right thing to
  reward in a *design*-replication task? The brief explicitly wanted a content
  dimension, and it discriminates beautifully (it's the term that separates rollouts),
  so I'd keep it — but surface the tension as a "learning," noting the model's
  paraphrasing is arguably sensible behavior that the content term penalizes.

That last point is exactly the "what behaviors/learnings emerge" the brief asks for. The
dominant, reproducible failure mode: **Opus 4.7 reconstructs design copy by paraphrase,
with fidelity inversely proportional to prose density** — backed by cross-method (OCR +
judge) agreement and the per-page curve.

In response, I added more **structure components** to the catalog (harder for Claude Code
to replicate), since I believe generation on structure can be pushed further too.

---

## Phase 9 — Why direct Anthropic API calls (not Claude Code) for generation

A retrospective on the generator tooling fork, since I kept second-guessing it:

1. **Controlled temperature per stage** — I can dial composition vs. creativity per
   stage, which is how the "diversity" effect gets engineered in.
2. **Control.** With all the projects I've done in **D.E. Shaw** as well, I've found
   Claude Code very hard to control — it has its own agentic scaffolding. A layered
   stage pipeline gave me more room for precise, engineered prompts.
3. **Parallelism control** — Claude Code is a sequential agentic loop; it can't be
   parallelized the same way. Direct API calls are lean and give more control over rate
   limiting.
4. **Separation of concerns** — generation is a *data pipeline* (structured inputs,
   structured outputs, deterministic validation); evaluation is an *agentic task*
   (autonomous reasoning, file-writing, iteration). Using the right tool for each
   concern is the design choice.

(Evaluation, by contrast, *is* an agentic task — so there I use Claude Code, whose
harness and error-handling are already built.)

---

## Phase 10 — Packaging the pipeline into commands

Once the pieces worked, I wrapped them into scripts so the whole thing is runnable by
someone cloning the repo.

**The eval → report → view flow (3 commands):**

```bash
# 1. Launch the eval — Claude Code + Opus 4.7, ×10 on Modal
PYTHONPATH=src .venv/bin/python scripts/evaluate.py \
    --task out/passed-batch-50/035_local-service_dark-techy_high/task \
    --name opus47-035 --yes
# clones the task, refreshes the baked grader, flips agent allow_internet,
# wires ANTHROPIC_API_KEY to both agent (--ae) and judge (--ve),
# runs harbor -k 10 -n 10, lands the job at jobs/opus47-035/

# 2. Generate the report
PYTHONPATH=src .venv/bin/python scripts/report.py jobs/opus47-035
# harvests per-trial reward.json + reward-details.json + renders →
# reports/model-eval/opus47-035/{scores.json, scores.csv, report.html}

# 3. View it
open reports/model-eval/opus47-035/report.html
```

**The generate → pull → curate flow (live Modal):**

```bash
# Prereqs (one-time): Modal auth + the Anthropic Secret
.venv/bin/modal token new
.venv/bin/modal secret list | grep anthropic-api-key
# if missing: .venv/bin/modal secret create anthropic-api-key ANTHROPIC_API_KEY="sk-ant-..."

# Generate a small test batch to a throwaway volume (keeps it cheap + isolated)
PYTHONPATH=src .venv/bin/python scripts/generate.py \
    --count 4 --concurrency 4 --volume webdesign-rl-test

# Pull it down (defaults --out to out/webdesign-rl-test/)
PYTHONPATH=src .venv/bin/python scripts/pull_artifacts.py --volume webdesign-rl-test

# Confirm the pulled layout chains into curate
PYTHONPATH=src .venv/bin/python scripts/curate.py \
    --batch out/webdesign-rl-test --out out/curated-test
```

A couple of notes I want to remember: **generate** needs the Modal token + the Secret;
**pull** needs only the Modal token (no Anthropic key). Using `--volume webdesign-rl-test`
keeps tests isolated from the real `webdesign-rl-artifacts` default; tear it down after
with `modal volume delete webdesign-rl-test`.

---

Things that I did today:
- Day started with improving the behavior of our generators. There were several header/footer errors due to which sites were not looking particularly good. Fixed that.
- I though we could add more content to archetypes to make our websites more diverse and practical. But then I thought more and decided on increasing the number of structure components to increase our generation diversity and give CC a good test on evalution.
- Worked on generaing these tasks at scale. Learnt a lot about modal and what sort of efficiency gains can we hack through that. Scheduled about 50 jobs.
- ~80% of the generations returned task which is a decent throughput. Others failed because our quality gate disqualified them. They were not good and failed our quality checks.
- Next step was efficient validation through claude code. Currently runs, 10 claude code trajs in parallel for a task, split across 2 processes. Felt this was fine and more parallelization could hit severe rate limits. how did I come up with this number - this is related to my current project at D.E. Shaw where I am preparing a test-triage agent. There I used Claude Agent SDK and found by test and trials that 20-25 claude code SDKs peform effieciently without much slowdown and rate limits. So jsut went through with it.
- Also generated an automated reporting system explained below which will be very helpful while looking at the results.
- While running evals, I found structure and content as the two major areas where CC w Opus4.7 fails a lot. I looked at lots of examples in the automated reports and found them to be true. Ran eye validations.
- For the night I have left the evals running on the 38 tasks that our generation pipeline generated.
- Plan is I will look at the reports and results tomorrow, select the evals which are diverse and tell me more about the model behavior.
- It does not feel like that I will be able to complete task 2 and 3 tomorrow. I am interested but I won't get enough time. Fine I can research and leave my solutions in .mds.
- But I will first make sure that all the documentations are present validating my research, my ideas and my work. I should effectively communicate what I tried, why I tried and how I tried.

## What the automated report shows (and why each panel helps)

`scripts/report.py` turns a 10× job into a self-contained `report.html` (plus
`scores.json` / `scores.csv` so every number is auditable). Seven panels, each there to
answer a specific question when I open it:

1. **Provenance** — model, task, attempt count, cost/timing. Every number is traceable
   to a known run.
2. **Per-trial score table** — the 10 rewards and their four terms, with
   median / mean ± std / min–max. The *distribution* is the deliverable, not a lone
   scalar; std is the reward noise, which matters for RL.
3. **Reward + per-term distributions** — box/strip plots. Spread and outliers at a
   glance: is the model consistent, or does one rollout crash to the floor?
4. **Per-term means** — bars across the four terms. Shows *where* the skill is — content
   weak, color near-ceiling — instantly.
5. **Per-page × per-term heatmap** — which page drags which term down. This is the panel
   that exposed *content degrades with prose density* (pricing bright, about/gallery
   dark).
6. **Worst per metric (reference vs candidate)** — for each term, the worst attempt's
   render beside the reference. Lets me *see* what a low score looks like and
   eyeball-confirm the metric is penalizing a real defect, not noise.
7. **Best-overall attempt vs reference (all pages)** — the top rollout side-by-side with
   the target across every page. The "higher reward = closer to target" claim, made
   visual.

The throughline: panels 2–5 tell me *how much* and *where*; panels 6–7 let me confirm
*why* — that the grader's ranking matches what my eye ranks. That visual cross-check is
the per-task validity argument.

---

## Open threads I'm still chewing on

- **Is my color metric working as expected?** It scores ~0.97 and is forgiving on
  white-background pages — I want to pressure-test it on tougher examples.
- **Expand the taxonomy** beyond 10 archetypes × 10 aesthetics for more diversity.
- **Make the generation pipeline async** once I've characterized the rate limits, to cut
  the ~8 min/site.
- **Try Claude Code as a generator** as an alternative, if time permits — the harness is
  already built.
- **Tune the four-term weights** from the monotonicity study instead of leaving them
  equal, then re-validate.

## Final day
- The trail results came back today, so I will be working on closely looking at them.
- I don't think I will get enough time for task 2 and 3 so I will be working on creating proper documentations so people can walk through my solution.
- However I would research on these two topics and think about my final solution.