# Generator Research — Scalable Generation of Good, Diverse Websites

> Distilled from a deep-research pass (22 primary sources fetched, 25 claims adversarially
> verified — 22 confirmed, 3 killed). Captured 2026-05-30. This is the **evidence base** for
> the generator; settled design decisions move into [`../generator_design.md`](../generator_design.md)
> with a pointer back here. The brief's central question this answers: *"How complex,
> human-like, and varied are the websites that get generated?"* — i.e. how to **make** sites
> varied/human-like at scale, and how to **measure** that they are.

---

## TL;DR — what the field actually does

1. **Backbone = a two-stage concept→code pipeline.** A cheap model emits diverse website
   *concepts/briefs*; a code-specialized model turns each brief into self-contained HTML.
   This is the proven, crawl-free, scales-to-millions pattern (WebSight 2M pairs, Web2Code
   60K pages).
2. **Diversity, in proven art, comes from an explicit concept-sampling prompt** — varied
   industries/layouts/colors/positions, batched ~10-at-a-time across many calls. It is
   *unstructured prose*, **not** a formal taxonomy. A structured taxonomy is a reasonable
   **extension**, but it is **not evidenced** — and persona-conditioning, the closest proxy,
   was **refuted** in our verification. Validate the taxonomy's marginal value by ablation;
   don't assume it.
3. **Render-in-the-loop visual critique is the strongest quality lever.** Re-render the
   generated page, feed the screenshot to a VLM critic, iterate 1–3 cycles. Measurable gains
   on multiple benchmarks. Pair it with a **strict zero-reward-for-invalid-render gate**
   (ReLook) to anchor renderability.
4. **Nobody measures corpus diversity/quality quantitatively** — this is exactly our
   "auditable good distribution" requirement, and our chance to show research taste. The
   tools the field offers: **Vendi Score** for diversity (no reference set needed) and
   **VLM-as-judge over ~9–10 rendered criteria** for quality.
5. **Two caveats bite us specifically:** every proven from-scratch generator is
   **single-page** (our ≥5-page coherence is unproven territory), and **WebSight's visual
   diversity partly comes from external Unsplash/CDN imagery we cannot use** (offline render).
   We must recover variety via **bundled assets / CSS / SVG**.

---

## 1. Scalable generation backbone — the proven pattern

**Two-stage LLM pipeline (concept model → code model).** This is the dominant, crawl-free
way the field generates web UIs at scale:

- **WebSight** (HuggingFace) — a smaller model (Mistral-7B-Instruct) generates *"a variety of
  website themes and designs"*; those concepts seed a larger code-trained model
  (Deepseek-Coder-33b) that emits the HTML. Scales to **2M HTML/screenshot pairs** (v0.2;
  v0.1 was 823K). *Source: arxiv 2403.09029.* **[confirmed 3-0]**
- **Web2Code** — uses GPT-3.5 to generate **60K HTML pages from scratch** under a 10-criteria
  prompt, then a two-stage GPT-4 instruction-augmentation step injecting Modern/Bootstrap
  styling. *Source: arxiv 2406.20098.* **[confirmed 3-0]**

**Takeaway for us:** adopt the **concept-model → code-model split as the backbone**. It is
the part of our "design-system-first multi-pass" leaning that is directly validated by prior
art. Our additions (a design-system spec, ≥5 coherent pages) sit on top of this proven base.

**Multi-stage, hierarchy-aware generation is an established quality lever.** *DesignCoder*
generates UI code via a UI-grouping chain (predict nested hierarchy) → divide-and-conquer
component-tree generation → vision-aware self-correction against the rendered output. This
supports a **brief → design-system → components → pages** structure. *Source: arxiv
2506.13663.* **[confirmed 3-0]** — *Caveat:* DesignCoder targets React-Native mobile (Appium
render), so web transfer is **inferred, not demonstrated**; and its specific quantitative
self-correction gains (MSE/CLIP/SSIM) were **refuted 0-3** — cite the architecture, not the
numbers.

---

## 2. Diversity / distribution control — what actually works (and what doesn't)

**What's proven: explicit concept-sampling prompts.** The field's main defense against
generic "SaaS-landing-page" sameness is simply *asking* for variety, in batches. The verbatim
WebSight prompt:

> *"Generate diverse website layout ideas for different companies, each with a unique design
> element. Examples include: a car company site with a left column, a webpage footer with a
> centered logo. Explore variations in colors, positions, and company fields… just give the
> list of 10 ideas."*

Worked examples span Fashion / Restaurant / Consulting / Real Estate / Education. *Source:
arxiv 2403.09029.* **[confirmed 3-0]**

**What's NOT proven (and a refutation):**
- The **structured taxonomy / grammar / MAP-Elites / quality-diversity** angle — central to
  our leaning — was **not evidenced by any surviving claim**. No cited web-UI generator uses
  it.
- **Persona-conditioning** (the closest proxy: condition generation on a large set of diverse
  personas to combat sameness) was **refuted 1-2** in verification. *Source: arxiv 2406.20094.*

**Implication.** Keep a WebSight-style concept prompt as the *proven base*. Layering a
structured taxonomy on top is a *reasonable, auditable extension* — its whole justification is
our "auditable distribution" requirement, which prose prompting cannot satisfy — but its
marginal diversity benefit over plain prompting is an **open question to settle by our own
ablation**, not an assumption. (See Open Questions.)

---

## 3. Quality / human-likeness — render-in-the-loop is the lever

**Front-end quality must be judged on rendered pixels, not source text.** LLMs are
comparatively weak at front-end (layout / visual-element recall) vs. algorithmic code.
*ReLook* and *Design2Code* both establish this. *Sources: arxiv 2510.11498, 2403.03163.*
**[confirmed 3-0]** — *Nuance:* Design2Code found GPT-4V output rated *better than the human
reference* in 64% of cases, so the weakness is concentrated in layout/visual recall, not
uniform.

**Re-render → VLM critic → iterate measurably improves quality.** Consistent across recent
work:
- *Vision-Guided Iterative Refinement*: VLM critic on rendered pages, **up to +17.8% over
  three refinement cycles** (10.8% in a Claude self-improvement setting). *arxiv 2604.05839.*
- *ReLook*: MLLM (Qwen2.5-VL-72B) scores rendered pages and supplies vision-grounded feedback;
  outperforms strong baselines across ArtifactsBench / FullStack-Bench-Html / Web-Bench.
  *arxiv 2510.11498.*
- *VisRefiner*: a `(GT_image, pred_image, pred_code)` triplet loop via headless Chromium gives
  a **stable +0.7** on Design2Code and Design2Code-HARD. *arxiv 2602.05998.*
- *WebGen-V*: structured single-turn refinement reduces low-spacing scores across all tested
  models. *arxiv 2510.15306.*

**[confirmed — mixed 3-0 / 2-1]** — *Caveat:* several gains are **modest** (sub-1-point on
100-scales) and rest on **single self-reported sources** with VLM-judge bias and only
fair-to-moderate human agreement. **Adopt the architecture; do not over-claim the numbers.**

**Enforce renderability with a hard gate.** *ReLook* applies a **strict zero-reward rule for
any invalid/failed render** — "if any required screenshot is invalid (render failure or
timeout), the reward is zero." This anchors renderability and prevents reward hacking, and is
directly transferable to both our generator's quality gate and the task reward. *arxiv
2510.11498.* **[confirmed 3-0]**

**VLM critique can approach human design judgment.** An LLM-driven pipeline (Gemini-1.5-pro /
GPT-4o) that iteratively refines design comments + bounding-box localizations from a UI
screenshot + guidelines produced critiques **human experts preferred over baseline, closing
the gap to human performance by 50%** on one metric. Supports using a VLM both to grade and as
a generator-side critic. *arxiv 2412.16829.* **[confirmed 3-0]** — *Caveat:* only *fair*
inter-rater reliability (Fleiss κ 0.22–0.29).

---

## 4. Measuring diversity & quality — how to DEFEND "good distribution"

This is the field's blind spot and our differentiator. **The proven generators report no
quantitative diversity or aesthetic metrics at all** — WebSight selects checkpoints "by
manually inspecting generated samples." *arxiv 2403.09029.* **[confirmed 3-0]**

**Diversity → Vendi Score.** The exponential of the Shannon entropy of the eigenvalues of a
sample-similarity matrix — an interpretable *"effective number of unique elements."*
Crucially, it **requires no reference dataset or distribution**: it scores the corpus from the
samples alone with a user-chosen similarity function (e.g. CLIP screenshot embeddings). Ideal
for auditing our generated set. *arxiv 2210.02410.* **[confirmed 3-0]**

**Quality → VLM-as-judge over rendered pages, ~9–10 criteria.** The field standard:
- *Web2Code WCGB*: render predicted HTML → GPT-4 Vision scores **10 criteria in 4 categories**
  (Visual Structure/Alignment, Color/Aesthetic, Textual Consistency, UI Interactivity), 0–10.
- *WebGen-V*: GPT-5 over **9 metrics in 3 categories** (Text, Media, Layout), 1–5.

*Sources: arxiv 2406.20098, 2510.15306.* **[confirmed 3-0]** — our existing `design_judge` is
exactly this shape; the rubric can be cross-referenced against WCGB's criteria.

**Graded variation → rule-based perturbations.** *VisRefiner* builds synthetic pairs via
**six controlled perturbation categories — color, layout, alignment, component, image, text —**
producing "visually perceivable yet structurally localized deviations" with traceable
code↔region mapping (~20K instances). This maps directly onto our existing perturbation
harness and could enrich it. *arxiv 2602.05998.* **[confirmed 3-0]**

---

## 5. Grading-side prior art

**Design2Code** is the most directly relevant grading benchmark, but it is **crawled, not
generated**: 484 manually curated real-world webpages (from C4/Common Crawl) with automatic
metrics (CLIP + block/text/position/color element matching). **Reuse its metric suite**, but
it offers no from-scratch generator and no corpus-diversity mechanism. *arxiv 2403.03163.*
**[confirmed 3-0]** Our grader already echoes this suite (SSIM/structure, color CIEDE2000,
content OCR, design_judge).

---

## 6. The synthesized recommended pipeline (medium confidence)

A **design-system-first, render-in-the-loop, taxonomy-driven generator**:

1. **Diversity:** structured taxonomy/grammar sampler (industry × layout-archetype ×
   visual-style × palette × type-scale) → expand each cell with a WebSight-style concept
   prompt → **Vendi-score + dedup** prune. Coverage tables make the distribution auditable.
2. **Coherence:** generate a **design-system spec once per site** (palette, bundled-font type
   scale, component library) → reuse it across **≥5 pages** (brief→design-system→
   components→pages, DesignCoder-style hierarchy). *This is the part no prior art validates —
   we must measure cross-page consistency ourselves.*
3. **Quality:** re-render each page **offline** (deterministic headless Chromium, bundled
   fonts, no external assets) → VLM critic for **1–3 refinement cycles** → **strict
   zero-reward gate on invalid render**.
4. **Measure:** **Vendi Score** over CLIP screenshot embeddings + taxonomy-coverage tables for
   *diversity*; a **WCGB/WebGen-V-style VLM-as-judge** over ~9–10 criteria for *quality*;
   near-duplicate rejection. Both feed the final report's "good distribution" defense.
5. **Assets:** replace WebSight's external Unsplash/CDN imagery with **bundled assets / CSS /
   SVG** to honor the offline-render constraint (see [`../generator_design.md`](../generator_design.md)).

**Why medium (not high) confidence:** the **structured-taxonomy** and **multi-page-coherence**
layers are *not* directly evidenced by surviving claims (persona-conditioning refuted 1-2; all
proven generators single-page), and our **offline / no-external-asset** constraint diverges
from WebSight's actual implementation. The *backbone* (concept→code), the *refinement loop*
(render-in-loop + zero-reward gate), and the *measurement* (Vendi + VLM-judge) are well
supported; the parts unique to our constraints are reasoned extensions to validate.

---

## 7. Open questions carried forward

1. **Multi-page coherence.** How do we enforce shared design tokens / nav / footer / type
   scale across ≥5 pages when all proven generators are single-page? Does "generate the
   design-system spec once and reuse per page" actually prevent per-page drift — and how do we
   *measure* cross-page consistency?
2. **Taxonomy vs. prose prompting.** Does a structured taxonomy / quality-diversity sampler
   produce more defensible, less mode-collapsed coverage than open-ended concept prompting,
   and at what cost? No surviving claim evidenced it — needs our own ablation.
3. **Vendi similarity function + threshold.** CLIP screenshot embeddings vs. structural/DOM
   features vs. layout embeddings? And what Vendi/coverage numbers count as "good
   distribution" to a reviewer?
4. **Does the refinement lift transfer?** The +10–18% gains are on *interactive* WebDev tasks.
   Does render-in-the-loop critique help our *static, screenshot-only, multi-page* setting —
   and can it run deterministically and cheaply on every site at scale under the offline +
   bundled-font constraints?

---

## Appendix — killed / refuted claims (do NOT cite)

- **Persona-conditioning combats mode collapse** — refuted 1-2 (arxiv 2406.20094).
- **WebGen-V structured 5-component representation substantially improves quality;
  degradation-F1 0.78 vs 0.46** — refuted 0-3 (arxiv 2510.15306). (The refinement *loop* is
  still supported; this *specific* structured-input superiority claim is not.)
- **DesignCoder vision-aware self-correction gains of 37.64% MSE / 9.52% CLIP / 12.82% SSIM**
  — refuted 0-3 (arxiv 2506.13663). (Adopt the architecture; drop these numbers.)

## Appendix — key sources

| Source | arXiv | Role |
|---|---|---|
| WebSight | 2403.09029 | Two-stage concept→code, 2M pairs, diversity prompt |
| Web2Code | 2406.20098 | 60K from-scratch pages; WCGB VLM-judge (10 criteria) |
| Design2Code | 2403.03163 | Grading benchmark + metric suite (crawled) |
| ReLook | 2510.11498 | Render-in-loop critic + zero-reward-invalid-render gate |
| Vision-Guided Iterative Refinement | 2604.05839 | +17.8% over 3 refinement cycles |
| VisRefiner | 2602.05998 | Triplet render loop; 6-category perturbations |
| WebGen-V | 2510.15306 | Gen-Eval-Refine; GPT-5 judge, 9 metrics |
| DesignCoder | 2506.13663 | Hierarchy-aware multi-stage + vision self-correction |
| (UI design critique) | 2412.16829 | VLM critique approaching human judgment |
| Vendi Score | 2210.02410 | Reference-free diversity metric |
