# 13 — Token-compliance scoping (exempt the frozen design system)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the first live single-site run — the
site was dropped on `components.css: literal value 16px is not a token`.

## What to build

The stage-4 **token-compliance** check currently flags any hex/rgb/px literal anywhere,
including in `components.css`, and (because that's a frozen shared artifact) drops the
whole site "site-wide" with no repair path. But the check's purpose is **anti-drift —
cross-page consistency** — and `components.css` is shared **identically** by every page,
so it *cannot* cause cross-page drift, and real design systems legitimately contain
structural literals (`border-radius: 16px`, `padding: 16px`). The check is scoped wrong.

Re-scope it to where drift can actually occur:
- **Enforce** token-compliance on **per-page styles** (stage-3 output: inline `style=""`
  and page-level `<style>` blocks) — a page introducing a new color/size is real drift and
  is repairable by the per-page nudge.
- **Exempt** the frozen design-system stylesheets (`variables.css`, `components.css`) from
  the literal check — they are the single source of truth, authored once, and define the
  values pages reference.
- (Optional, if cheap) keep a **color-palette coherence** signal — `components.css` colors
  should come from `variables.css` tokens — since palette identity matters even though px
  structure doesn't. Decide based on effort; not required for stability.

## Acceptance criteria

- [ ] `components.css` containing structural px literals passes the gate.
- [ ] A page with an off-token color/size in inline/`<style>` still **fails** (and is
      repairable per-page, not a site-wide drop).
- [ ] `variables.css` / `components.css` exempt from the literal check.
- [ ] The existing token-compliance test is updated (the "components.css off-token fails"
      assertion changes to per-page scope); full suite green.
- [ ] The live `saas-landing / swiss-editorial / low` seed now clears token-compliance.

## Blocked by

- None — can start immediately. (Highest priority with 08: together they gate a passing,
  navigable site.)
