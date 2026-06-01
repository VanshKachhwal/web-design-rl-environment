# PRD: Web Design Site Generator (Part 1 V1)

Status: ready-for-agent

> Scope: the **generator** only — the pipeline that produces the **reference target sites**
> a coding agent replicates. The grader (4-term), the render module, and Harbor emit
> packaging are already built (issues 01–08) and are *consumers* of this output, not part of
> this PRD. Animations (Part 2) and additional frameworks (Part 3) are out of scope.
> Grounded in `docs/design/generator_design.md` (3-stage pipeline, quality gate,
> well-posedness constraints, Modal scale, grilled V1 decisions) and
> `docs/design/task_selection.md` (deferred curation metric).

## Problem Statement

We have a validated grader, a deterministic render module, and Harbor task packaging — but
**nothing that produces the reference sites they consume**. The brief requires tasks built
from **≥10 multi-page websites generated from scratch** (no crawling), each **≥5 pages**,
spanning a **good distribution** of site types, and **complex / human-like / varied**.

The naive approach — one LLM call per "5-page website" — fails two ways: it **mode-collapses**
(every site becomes the same template, killing the distribution requirement) and it
**drifts** (each page re-invents the styling, so a "site" is really five unrelated pages).
Worse, a generated site is only a usable RL target if it is **well-posed**: everything the
agent must reproduce has to be *visible in a single 1280px static screenshot* and
*faithfully re-renderable in the sealed offline env* — otherwise the agent is asked to
replicate something it structurally cannot. None of this generation machinery exists yet
(`generate/` is empty stubs).

## Solution

A **multi-stage, diversity-first generation pipeline** that produces static HTML/CSS
multi-page sites, gates them for validity and well-posedness, and runs at scale on Modal —
overgenerating a pool, filtering it, and curating the final committed fixtures.

**The 3-stage pipeline (per site):**

1. **Big picture** — a *sampled seed* (industry × aesthetic × complexity, drawn in code, not
   by the model) → a brand brief, a sitemap with slugs (the `page_map`), a per-page section
   list, and a **component manifest** (the deduplicated set of component types the site
   needs). One call, high temperature: diversity comes from the sampled inputs.
2. **Design system as frozen code** — the spec → `variables.css` (tokens), `components.css`
   (the manifest's components styled for this aesthetic), and header/footer/nav partials.
   One coherent call. This is *frozen*; consistency lives in these shared artifacts.
3. **Per-page fan-out** — one call per page, each reading the frozen artifacts read-only and
   **composing** them into markup (referencing only declared tokens/classes). Pages are
   consistent by construction, not by the model remembering to be.

**The quality gate** verifies each site is a *valid, faithfully-replicable target*: stage-4
deterministic checks (completeness, target-identity, per-page substance, token/manifest
compliance, chrome identity, hermeticity, static-only) and stage-5 render validity at 1280px.
Failures are repaired **locally** — fail-fast inline gates after stages 1 and 2, and a
bounded stage-3 nudge loop — or the site is **dropped** (the gate is a filter on a stream).

**Generation at scale** runs the per-site pipeline as a Modal `.map()` over a stratified
seed list, **in the same sealed image** that renders and grades — so reference screenshots
are produced in the exact environment they're graded in. We **overgenerate (~48) → gate →
curate 10** committed fixtures, which the existing emit packaging turns into Harbor tasks.

**Fonts** are made faithful: a curated open-licence palette installed **OS-level** in the
render/verifier image and referenced by bare family name, with agent screenshots rendered
**in-container** — which supersedes the deferred `@font-face` patch (issue 09).

## User Stories

1. As an RL engineer, I want sites **generated from scratch** by an LLM pipeline (no crawling), so I comply with the brief's hard requirement and own the full design.
2. As an RL engineer, I want each site to have **≥5 pages** (bounded ≤10), so every task meets the multi-page requirement without unbounded render cost.
3. As an RL engineer, I want diversity driven by **code-sampled seed axes** (archetype × aesthetic × complexity) rather than model variance, so the batch spans the space instead of collapsing to coffee shops and SaaS dashboards.
4. As an RL engineer, I want each site's **seed tuple recorded**, so the batch's coverage is auditable, re-runnable, and usable as a cheap diversity signal for curation.
5. As an RL engineer, I want the page count **coupled to the complexity axis** (low→5–6 … high→up to 10), so "complex" sites are both denser and broader and the complexity axis stays coherent.
6. As an RL engineer, I want stage 1 to emit a **sitemap with stable slugs** (home→`index`, slugify, collision suffix), so page identity is deterministic and everything downstream derives from one token.
7. As an RL engineer, I want stage 1 to emit a **component manifest** (the union of component types any page needs), so stage 2 has an exact checklist and pages can't reference unstyled components.
8. As an RL engineer, I want stage 1 to own **naming/anchoring copy** (headings, nav, CTAs, tier names, brand) and stage 3 to own **filling copy** (paragraphs, blurbs, list items), so the spec is authoritative on identity while pages read naturally.
9. As an RL engineer, I want stage 2 to author the design system **as real CSS files** (`variables.css` + `components.css` + partials), not prose, so consistency is enforced by shared artifacts and not re-interpreted per page.
10. As an RL engineer, I want `variables.css` to lock **values** (palette, type scale, spacing, radius) and `components.css` to lock **component structure**, so neither value drift nor structural drift can appear across pages.
11. As an RL engineer, I want stage 2 to author **exactly the manifest's components** styled for the site's aesthetic, drawn from a **canonical catalog**, so CSS stays lean and the vocabulary is bounded and checkable.
12. As an RL engineer, I want header/footer/nav shipped as **byte-identical injected partials**, so chrome is provably identical across pages.
13. As an RL engineer, I want stage 2 to be a **single coherent call** (not fanned out), so components share one design language (radius, shadow, spacing) instead of drifting from each other.
14. As an RL engineer, I want stage 3 to **compose** the frozen artifacts and reference **only declared tokens/classes**, so a page can introduce no new color, size, or component.
15. As an RL engineer, I want stage 3 fanned out **one call per page in parallel**, so generation is fast and pages stay independent while binding to the same frozen system.
16. As an RL engineer, I want every visual to be **CSS-drawable / solid-color placeholder / SVG pattern only** (no raster assets), so the agent can reproduce 100% of what it sees and the task stays well-posed.
17. As an RL engineer, I want the site to be **hermetic** (no external fonts/images/CSS/JS), so the sealed offline render is faithful and the emitted task is portable (Docker↔Modal).
18. As an RL engineer, I want the site to be **static** (no `<script>`, no `@keyframes`/`animation`, no interaction-revealed content), so the single static capture is the complete design and the agent can recover it.
19. As an RL engineer, I want fonts restricted to a **curated open-licence palette installed OS-level** and referenced by bare family name, so the agent's `font-family: Inter` resolves in the verifier render and typography is faithful, not DejaVu-substituted.
20. As an RL engineer, I want the **agent's reference screenshots rendered in the same sealed image** as grading, so host/container font drift (the issue-07/09 bug) cannot make the agent study a different design than it's graded against.
21. As an RL engineer, I want one **fonts manifest** as the single source of truth feeding the image install, the generation allow-list, and the gate's hermeticity check, so the three never diverge.
22. As an RL engineer, I want a **stage-4 deterministic gate** (completeness, target-identity, substance, token/manifest compliance, chrome identity, hermeticity, static-only), so broken/drifted/degenerate sites are rejected cheaply before any render or judge.
23. As an RL engineer, I want a **stage-5 render-validity gate** at 1280px (renders clean, deterministic, not blank, no catastrophic layout), so only sites that render correctly and reproducibly survive.
24. As an RL engineer, I want a **per-page substance floor** (≥3 distinct catalog components, ≥50 words, height ∈ [600px, 12000px]), so every page is a real replication challenge and no near-empty page dilutes the task.
25. As an RL engineer, I want the gate to return **exact diagnostics** (which check failed, where), so repair can nudge with a precise machine error rather than "make it better."
26. As an RL engineer, I want **fail-fast inline gates** after stage 1 (sitemap ≥5, manifest well-formed) and stage 2 (manifest compliance), so a doomed site dies before paying for downstream calls.
27. As an RL engineer, I want stage-3 failures repaired by **re-invoking the failing page with the exact error, ≤2 times**, then dropping the site, so repair is localized and bounded and never re-rolls the whole site.
28. As an RL engineer, I want page repair to stay **composition-only against the frozen artifacts**, so fixing one page can never re-author the design system and drift the others.
29. As an RL engineer, I want every **dropped site logged with its reason**, so a systematic failure mode is a prompt bug to fix upstream rather than silent attrition.
30. As an RL engineer, I want generation to use **Opus 4.6 for all three stages** at temperatures 1.0/0.7/0.6, so creativity/coherence are maximized with a single model, tunable later.
31. As an RL engineer, I want the LLM accessed behind a **thin stubbable client**, so the deterministic logic (prompt building, parsing, gate) can be tested without live API calls.
32. As an RL engineer, I want the per-site pipeline runnable **once locally** end-to-end, so I can eyeball a single site's quality before paying to fan out.
33. As an RL engineer, I want the pipeline fanned out on **Modal `.map()` over a stratified seed list, in the sealed image**, so generation load stays off my machine and references are produced where they're graded.
34. As an RL engineer, I want site artifacts written to a **Modal volume keyed by seed id**, so a dropped site doesn't lose the others and re-runs are addressable.
35. As an RL engineer, I want a **concurrency cap / backoff** on the fan-out, so ~48 sites × ~15 calls don't trip Anthropic rate limits.
36. As an RL engineer, I want to **overgenerate ~48 → gate → keep ~10**, so the curated set has coverage and yield headroom and the gate pass-rate is a measured "stable recipe" number I can report.
37. As an RL engineer, I want a **V1 curation shortlist** (distinct archetype + distinct aesthetic + complexity spread ~3/4/3) followed by a human confirmation pass, so the final 10 demonstrably span the distribution.
38. As an RL engineer, I want each surviving site handed to the **existing emit packaging**, so generation produces runnable Harbor tasks with no change to the packaging layer.
39. As an RL engineer, I want the curated 10 **committed as fixtures**, so the deliverable is reproducible (judges run the exact sites) even though LLM generation itself is non-deterministic.
40. As a coding agent, I want a faithfully-renderable, fully-CSS, static, single-viewport target, so the screenshots I'm given are something I can actually reproduce in HTML/CSS.
41. As a maintainer, I want the deterministic modules (taxonomy/seeds/slug, the gate's stage-4 checks, curation) covered by **behavior tests**, so refactors don't silently break diversity, identity, or the validity guarantees.
42. As a maintainer, I want the canonical **component catalog and taxonomy axes defined in one place**, so generation, the manifest, the gate, and curation all reference the same vocabulary.

## Implementation Decisions

**Module decomposition (deep modules, simple stable interfaces):**

- **`taxonomy`** — pure data + enumeration. Defines the stratified axes (`archetype` ~10,
  `aesthetic` ~10, `complexity` 3) and free modifiers (`audience/region`, `brand-mood`);
  per-archetype **page menus** (core ≥5 + optional, total ≤10); and the **canonical
  component catalog** (~20 types: chrome, atoms, sections). Interface: enumerate the
  coverage grid; look up an archetype's page menu and legal components.
- **`seeds`** — stratified sampler over the taxonomy grid → a deterministic ordered list of
  **seed tuples** (given a count + a fixed ordering, no RNG that breaks reproducibility);
  and an expander turning one seed into a promptable spec object.
- **`slug` / `page_map`** — pure derivation: sitemap page titles → slugs (home→`index`;
  slugify lowercase/ASCII-fold/hyphenate/≤40 chars; collision → numeric suffix; reserve
  `variables`/`components`/`fonts` stems) → `page_map = {slug: {screenshot, expected_file}}`.
- **Stage runners** `stage1` / `stage2` / `stage3` — each builds a prompt, calls the LLM via
  a **thin stubbable client**, and parses the response into typed output. `stage1`: seed →
  brief + sitemap(+slugs/`page_map`) + per-page section list + component manifest. `stage2`:
  spec → `variables.css` + `components.css` + partials. `stage3`: spec + frozen artifacts +
  one page's section list → that page's HTML.
- **`quality_gate`** — stage-4 deterministic checks + stage-5 render validity (reuses the
  built render module). Interface: `(site_dir, spec) → GateResult{passed, diagnostics[]}`,
  where each diagnostic is a precise, repair-ready message scoped to a page/file.
- **Generator orchestrator** (`llm_site_generator`) — `generate_site(seed) → site_dir |
  Dropped(reason)`: stage1 → inline gate (≤2 re-rolls) → stage2 → inline manifest gate (≤2
  re-rolls) → stage3 fan-out → gate(4/5) → stage-3 nudge loop (≤2/page) → emit; logs drops.
- **`fonts`** — the fonts manifest (one source of truth) + the image change to install the
  vendored `.ttf` palette OS-level (`/usr/share/fonts` + `fc-cache`, editing the emit
  verifier Dockerfile) + rendering agent screenshots in-container (the issue-09 supersession).
- **Modal batch runner** — `.map()` `generate_site` over the seed list in the sealed image,
  write artifacts to a volume keyed by seed id, concurrency cap.
- **`curation`** — V1 greedy coverage shortlist over seed tuples (distinct archetype +
  aesthetic + complexity spread) → 10 candidates for a human confirmation pass.

**Data contracts:**

- **Seed tuple**: `(archetype, aesthetic, complexity, audience, brand_mood)` — recorded per
  site for auditability and curation.
- **Spec** (stage-1 output): brief, sitemap (ordered pages with slugs → `page_map`),
  per-page section list, component manifest (subset of the canonical catalog).
- **Design system** (stage-2 output): `variables.css`, `components.css`, header/footer/nav
  partials — the frozen artifacts stages 3 binds to.
- **`page_map`**: `{ slug: { "screenshot": "<slug>.png", "expected_file": "<slug>.html" } }`
  — the same shape the built emit/grader already consume.
- **`GateResult`**: `{ passed: bool, diagnostics: [ { check, page/file, message } ] }`.

**Grilled V1 decisions (see `generator_design.md` for the full table):** CSS/SVG-only
imagery (no raster); 8-family OFL palette (Inter, Work Sans, Space Grotesk, Archivo,
Playfair Display, Source Serif 4, Poppins, JetBrains Mono) + DejaVu fallback, display faces
headings-only; substance floor 3-components/50-words/height∈[600,12000]; static-only
forbid-list (`<script>`, `@keyframes`/`animation`, interaction-reveals) with `transition` +
cosmetic hover allowed and disclosure components rendered open; Opus 4.6 all stages at
1.0/0.7/0.6; ≤2 nudges / ≤2 re-rolls; ~48 generated → keep 10.

**Build order:** generate **one site locally and eyeball it**, then run the **~48-site batch
on Modal** → gate → curate 10. No intermediate "calibration" phase.

**Font / issue-09 supersession:** the OS-level palette + in-container agent-screenshot render
**replaces** the `@font-face` patch planned in `.scratch/grader-mvp/issues/09-*`; that issue
should be re-statused as superseded rather than built as written.

## Testing Decisions

**What makes a good test here:** assert each module's **external behavior** — the output a
given input produces — not internal implementation. Tests are deterministic, so they target
the deterministic modules and stub the LLM client entirely (no live API calls).

**Modules to test (per developer decision):**

- **Pure helpers (`taxonomy` / `seeds` / `slug`)**: the coverage grid enumerates the
  expected axis cells; stratified sampling is **deterministic** (same count/order → same seed
  list) and **spans** the grid; slug derivation handles home→`index`, slugifies titles,
  resolves collisions with suffixes, and rejects/repairs reserved stems; `page_map` derives
  one consistent token into `<slug>.html` + `<slug>.png` + key.
- **`quality_gate` stage-4 checks (highest value)**: against **fixture sites**, each check
  fires correctly and in isolation — token compliance flags an off-token value; manifest
  compliance flags a referenced-but-unstyled component; hermeticity flags an external
  font/image/CSS/JS and passes an inert external `<a>`; substance floor fails a near-empty
  page and passes a rich one; static-only fails `<script>`/`@keyframes`/interaction-reveal
  and passes `transition`/cosmetic hover; target-identity fails a missing/mismatched page.
  Diagnostics are precise enough to drive repair.
- **`curation` shortlist**: given a synthetic survivor pool with known seed tuples, selection
  returns 10 with distinct archetypes/aesthetics and the target complexity spread, and dedupes
  same-cell candidates.

**Explicitly not unit-tested:** the **stage runners' live LLM calls** (stub the client; test
only prompt assembly + response parsing if useful), the **orchestrator repair loop** and the
**Modal batch runner** (integration concerns — exercised by the local single-site run, not
unit tests).

**Prior art:** mirror the grader's tests — `pytest` (+`pytest-asyncio`), small hand-made
**fixture sites** checked into test data (the grader already uses fixture sites and the
oracle), and the same "identical→pass / degenerate→fail / each-check-in-isolation" shape.

## Out of Scope

- **The quantitative coverage metric** for curation — deferred to `task_selection.md`; V1
  uses the greedy shortlist + human pass.
- **The eval/report harness** (run Opus 4.7 ×10 per task → render → grade → visualize) — the
  brief's results deliverable, downstream of generation, designed separately.
- **Part 2 (animations)** and **Part 3 (React/Tailwind/Solid)** — only the static/Part-1
  path is built; their seams already exist in the grader/render design.
- **Photographic / raster assets shipped to the agent** — the post-V1 upgrade noted in the
  design doc; V1 is CSS/SVG-only.
- **Reward-weight tuning** and any grader changes — the grader is fixed; this PRD only
  produces the targets it scores.

## Further Notes

- The generator's acceptance test *is* the gate: a site that doesn't pass stage 4/5 is not a
  valid target. The gate also reuses the render module already built (issue 05), so stage 5
  is wiring, not new rendering code.
- "Stable recipe" (the brief's hard requirement #1) is operationalized as a **measured gate
  yield** reported from the first real batch, not asserted.
- Grader-discriminability on a given target is deliberately **not** a generation gate — it is
  characterized later in the validation report; we generate the full distribution and let the
  report expose where discrimination is softer (see `generator_design.md`).
- Confirm the exact **Opus 4.6 model ID** (`claude-opus-4-6`) when wiring; the canonical list
  only spells out `claude-opus-4-8`.
