"""Orchestrate the 3-stage pipeline into a renderable, gated site directory.

Two entry points live here:

- :func:`generate_site` — the **assembler**. Runs stage 1 -> 2 -> 3 (fanned out
  per page) through the stubbable
  :class:`~webdesign_rl.generate.client.GenerationClient` and writes the results
  into a static HTML/CSS site on disk (the frozen stylesheets, one ``<slug>.html``
  per page with byte-identical chrome, ``page_map.json``, ``seed.json``). It does
  *no* gating — it is the minimal end-to-end skeleton.

- :func:`generate_gated_site` — the **per-site orchestrator** wrapping the
  assembler with the quality gate and bounded repair (issue 04):

    stage 1 -> inline gate (sitemap >=5, manifest well-formed; <=2 re-rolls,
              else skip the seed)
    stage 2 -> inline manifest-compliance gate (<=2 re-rolls, else skip)
    stage 3 fan-out -> assemble -> full gate (stage 4 + stage 5)
    -> stage-3 nudge loop: a failing page is re-generated with the *exact*
       diagnostic appended (<=2 nudges/page), **composition-only** (the frozen
       stylesheets are never re-authored), then the site is **dropped**
    -> mechanical fixes (no LLM call) where unambiguous
    -> return the site dir, or :class:`Dropped(reason)`.

Every drop is **logged with its reason** (no silent attrition), so a systematic
failure mode surfaces as an upstream prompt bug rather than disappearing.

Consistency is by construction: every page links the same frozen stylesheets and
embeds the same chrome, and repair is composition-only, so no page can drift the
palette, components, or navigation.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from . import stages, taxonomy
from .quality_gate import (
    GateResult,
    _styled_classes,
    run_stage4_gate,
    run_stage5_gate,
)
from ..render.browser import render_site

logger = logging.getLogger(__name__)

# The two frozen stylesheets every page links — and the *only* stylesheets a page
# may reference (the token/manifest-compliance contract).
VARIABLES_CSS = "variables.css"
COMPONENTS_CSS = "components.css"

# Bounded-repair budgets (design decision #11).
MAX_REROLLS = 2          # inline stage-1 / stage-2 re-rolls before skipping seed
DEFAULT_MAX_NUDGES = 5   # default stage-3 nudges per page before dropping (issue 10)
MIN_PAGES = 5            # the sitemap floor

# Diagnostics on these "pages" are site-wide / shared-artifact failures that the
# composition-only stage-3 nudge cannot fix — they force an immediate drop.
_SHARED_TARGETS = frozenset({VARIABLES_CSS, COMPONENTS_CSS, "page_map.json", None})


@dataclass(frozen=True)
class Dropped:
    """A site the orchestrator declined to keep, with the machine reason why.

    ``check`` names the fatal gate/inline-gate check that forced the drop (e.g.
    ``"substance"``, ``"chrome-identity"``, ``"stage-1-inline"``). It is a new,
    defaulted field so existing call sites constructing ``Dropped(reason=...)``
    stay valid; the Modal batch's per-check telemetry attributes drops by it.
    """

    reason: str
    check: str | None = None


def generate_site(seed, client, out_dir) -> Path:
    """Run the 3-stage pipeline and write a renderable site to ``out_dir``.

    This is the un-gated assembler (issue 01). For the gated, repaired pipeline
    use :func:`generate_gated_site`.

    Returns the ``Path`` to the written site directory (frozen stylesheets, one
    HTML file per page, ``page_map.json``, ``seed.json``).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = stages.run_stage1(seed, client)
    design = stages.run_stage2(spec, client)
    _write_shared(out_dir, design)

    for page in spec.pages:
        body = stages.run_stage3(spec, design, page, client)
        _write_page(out_dir, page, body, design)

    (out_dir / "page_map.json").write_text(json.dumps(spec.page_map, indent=2))
    (out_dir / "seed.json").write_text(json.dumps(seed, indent=2))
    return out_dir


def generate_gated_site(seed, client, out_dir, *, render=render_site,
                        max_nudges=DEFAULT_MAX_NUDGES, stats=None):
    """Run the gated, bounded-repair pipeline for one site.

    Args:
        seed: the sampled seed dict.
        client: a :class:`GenerationClient` (stub in tests, Anthropic in prod).
        out_dir: directory to write the site into.
        render: the render callable (``render_site`` by default; injectable so
            tests drive stage 5 with canned images without launching Chromium).
        max_nudges: per-page stage-3 nudge budget before the site is dropped
            (default :data:`DEFAULT_MAX_NUDGES` = 5; tunable without a code edit).
        stats: an optional mutable dict the gate populates with per-check
            telemetry — ``nudges_by_check`` (a ``{check: count}`` mapping) and
            ``gate_rounds`` (the number of full-gate evaluations). Default
            ``None`` means **no behavior change**: nothing is collected and the
            pipeline runs exactly as before. The Modal batch passes a collector
            so ``summarize_batch`` can attribute nudge-churn to a check.

    Returns:
        The ``Path`` to a gated site that passed stage 4 + 5, or a
        :class:`Dropped` carrying the machine reason the site was discarded /
        the seed skipped (with the fatal ``check`` named).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Stage 1 + inline gate (<=2 re-rolls, else skip the seed) ----------
    spec = None
    for attempt in range(MAX_REROLLS + 1):
        logger.info("stage 1: generating brief + sitemap")
        spec = stages.run_stage1(seed, client)
        problem = _stage1_inline_problem(spec)
        if problem is None:
            slugs = [page["slug"] for page in spec.pages]
            logger.info("stage 1: %d pages %s", len(spec.pages), slugs)
            break
        if attempt == MAX_REROLLS:
            return _drop(seed, f"stage-1 inline gate failed after "
                               f"{MAX_REROLLS} re-rolls: {problem}",
                         check="stage-1-inline")
        logger.info("stage 1: re-rolling (attempt %d/%d): %s",
                    attempt + 1, MAX_REROLLS, problem)
    # --- Stage 2 + inline manifest-compliance gate (<=2 re-rolls) ----------
    design = None
    for attempt in range(MAX_REROLLS + 1):
        logger.info("stage 2: authoring frozen design system")
        design = stages.run_stage2(spec, client)
        problem = _stage2_inline_problem(spec, design)
        if problem is None:
            logger.info("stage 2: %d manifest component(s) styled",
                        len(spec.component_manifest))
            break
        if attempt == MAX_REROLLS:
            return _drop(seed, f"stage-2 inline manifest gate failed after "
                               f"{MAX_REROLLS} re-rolls: {problem}",
                         check="stage-2-inline")
        logger.info("stage 2: re-rolling (attempt %d/%d): %s",
                    attempt + 1, MAX_REROLLS, problem)

    _write_shared(out_dir, design)

    # --- Stage 3 fan-out + assemble ----------------------------------------
    total = len(spec.pages)
    for i, page in enumerate(spec.pages, start=1):
        logger.info("stage 3: page %d/%d: %s", i, total, page["title"])
        body = stages.run_stage3(spec, design, page, client)
        _write_page(out_dir, page, body, design)
    (out_dir / "page_map.json").write_text(json.dumps(spec.page_map, indent=2))
    (out_dir / "seed.json").write_text(json.dumps(seed, indent=2))

    # Mechanical, no-LLM fixes for unambiguous violations.
    _apply_mechanical_fixes(out_dir, spec)

    # --- Full gate (stage 4 + 5) + stage-3 nudge loop ----------------------
    return _gate_and_repair(seed, spec, design, out_dir, client, render,
                            max_nudges, stats)


# --- Inline-gate predicates -------------------------------------------------


def _stage1_inline_problem(spec):
    """A machine reason stage-1 output is doomed, or ``None`` if it is well-formed.

    Checks the two cheap invariants stage 1 owns: the sitemap has >=5 pages and
    the component manifest is well-formed (non-empty and drawn from the legal
    catalog).
    """
    if len(spec.pages) < MIN_PAGES:
        return (f"sitemap has only {len(spec.pages)} page(s); need "
                f">={MIN_PAGES}")
    if not spec.component_manifest:
        return "component manifest is empty"
    legal = taxonomy.legal_components()
    illegal = [c for c in spec.component_manifest if c not in legal]
    if illegal:
        return (f"component manifest has non-catalog component(s) {illegal}")
    return None


def _stage2_inline_problem(spec, design):
    """A machine reason stage-2 output is doomed, or ``None``.

    Manifest compliance: stage 2 must have styled a rule for every manifest
    component — the one failure a stage-3 nudge cannot fix cleanly, so catch it
    before any page is generated.
    """
    styled = _styled_classes(design.components_css)
    missing = [c for c in spec.component_manifest if c not in styled]
    if missing:
        return (f"components.css styles no rule for manifest component(s) "
                f"{missing}")
    return None


# --- Gate + repair ----------------------------------------------------------


def _gate_and_repair(seed, spec, design, out_dir, client, render, max_nudges,
                     stats=None):
    """Run the full gate; nudge failing pages <=max_nudges; else drop the site.

    When ``stats`` is a dict, it is populated with per-check telemetry — a
    ``nudges_by_check`` ``{check: count}`` mapping (one increment per nudged
    check) and a ``gate_rounds`` count of full-gate evaluations — so the batch
    can attribute nudge-churn (and drops) to a check. ``stats is None`` collects
    nothing (no behavior change).
    """
    nudges_used = {page["slug"]: 0 for page in spec.pages}
    page_by_html = {f"{page['slug']}.html": page for page in spec.pages}

    while True:
        logger.info("gate: running stage 4 + stage 5")
        _bump(stats, "gate_rounds")
        result = _full_gate(out_dir, spec, render)
        if result.passed:
            logger.info("gate: passed; keeping site")
            return out_dir

        checks = sorted({d["check"] for d in result.diagnostics})
        logger.info("gate: failed %d check(s) %s",
                    len(result.diagnostics), checks)
        by_page = _group_by_page(result.diagnostics)

        # Site-wide / shared-artifact failures cannot be repaired by a
        # composition-only page nudge -> drop immediately.
        shared = [t for t in by_page if t in _SHARED_TARGETS]
        if shared:
            diag = by_page[shared[0]][0]
            return _drop(seed, f"unrepairable site-wide failure: "
                               f"{diag['message']}", check=diag["check"])

        # Any failing target that is not a known page is also unrepairable.
        unknown = [t for t in by_page if t not in page_by_html]
        if unknown:
            diag = by_page[unknown[0]][0]
            return _drop(seed, f"unrepairable failure on '{unknown[0]}': "
                               f"{diag['message']}", check=diag["check"])

        # Repair each failing page with its exact diagnostic, bounded.
        for html_name, diagnostics in by_page.items():
            page = page_by_html[html_name]
            slug = page["slug"]
            if nudges_used[slug] >= max_nudges:
                diag = diagnostics[0]
                return _drop(
                    seed,
                    f"page '{html_name}' still failing after {max_nudges} "
                    f"nudges; last diagnostic: {diag['message']}",
                    check=diag["check"],
                )
            nudges_used[slug] += 1
            for diag in diagnostics:
                _bump_check(stats, diag["check"])
            message = " ; ".join(d["message"] for d in diagnostics)
            logger.info("repair: nudging %s (attempt %d/%d): %s",
                        slug, nudges_used[slug], max_nudges, message)
            body = _nudge_page(spec, design, page, client, message)
            _write_page(out_dir, page, body, design)
            _apply_mechanical_fixes(out_dir, spec)


def _full_gate(out_dir, spec, render):
    """Stage 4 then stage 5, combined into one GateResult."""
    stage4 = run_stage4_gate(out_dir, spec)
    stage5 = run_stage5_gate(out_dir, spec.page_map, render=render)
    diagnostics = list(stage4.diagnostics) + list(stage5.diagnostics)
    return GateResult(passed=not diagnostics, diagnostics=diagnostics)


def _nudge_page(spec, design, page, client, diagnostic_message):
    """Re-invoke stage 3 for one page with the exact diagnostic appended.

    Composition-only: this re-runs stage 3 (which reads the *frozen* stylesheets
    read-only and emits only the page body) with the machine error appended to
    the prompt — it can never re-author the design system. The model output is
    normalized to chrome-free ``<main>`` content (:func:`stages.normalize_stage3_body`)
    exactly like :func:`stages.run_stage3`, so a repair that re-adds in-body
    chrome (the unrepairable live failure) is stripped instead of duplicating
    the injected chrome.
    """
    prompt = stages.build_stage3_prompt(spec, design, page)
    prompt += (
        "\n\nThe previous attempt FAILED the quality gate with this exact "
        f"machine diagnostic:\n{diagnostic_message}\n"
        "Fix ONLY this page's body markup to resolve it. Do not change the "
        "design system (variables.css / components.css); compose only the "
        "existing component classes and declared var(--…) tokens."
    )
    raw = client.complete(prompt, temperature=stages.STAGE3_TEMPERATURE)
    return stages.normalize_stage3_body(raw)


def _group_by_page(diagnostics):
    """Group diagnostics by their ``page`` target, preserving insertion order."""
    grouped = {}
    for diag in diagnostics:
        grouped.setdefault(diag["page"], []).append(diag)
    return grouped


def _bump(stats, key):
    """Increment ``stats[key]`` by one when collecting (``stats`` is a dict)."""
    if stats is not None:
        stats[key] = stats.get(key, 0) + 1


def _bump_check(stats, check):
    """Increment the per-check nudge counter under ``stats['nudges_by_check']``."""
    if stats is not None:
        by_check = stats.setdefault("nudges_by_check", {})
        by_check[check] = by_check.get(check, 0) + 1


def _drop(seed, reason, *, check=None):
    """Log a drop with its reason and return the :class:`Dropped` sentinel.

    ``check`` (the fatal gate/inline-gate check name) rides along on the
    ``Dropped`` so the batch can attribute the drop cause by check.
    """
    seed_id = seed.get("seed_tuple", seed)
    logger.warning("dropping site for seed %s: %s", seed_id, reason)
    return Dropped(reason=reason, check=check)


# --- Mechanical fixes (no LLM call) -----------------------------------------


def _apply_mechanical_fixes(out_dir, spec):
    """Apply unambiguous, no-LLM repairs to the written pages.

    Currently a no-op for the gate's actual diagnostics: a literal that exactly
    equals a declared token is already accepted by token-compliance, and an
    external ``<a href=http>`` is already allowed (inert) by hermeticity. This
    seam exists so mechanical fixes (which must never call the model) are clearly
    separated from the LLM nudge loop.
    """
    return None


# --- Assembly helpers (shared by both entry points) ------------------------


def _write_shared(out_dir, design):
    (out_dir / VARIABLES_CSS).write_text(design.variables_css)
    (out_dir / COMPONENTS_CSS).write_text(design.components_css)


def _write_page(out_dir, page, body, design):
    html = _assemble_page(page["title"], body, design)
    (out_dir / f"{page['slug']}.html").write_text(html)


def _assemble_page(title: str, body: str, design: stages.DesignSystem) -> str:
    """Wrap stage-3 body markup into a full, hermetic, static HTML document.

    Links only the two frozen stylesheets and injects the header + footer
    partials byte-identically (the same strings for every page), so chrome
    identity and stylesheet-only referencing hold by construction. The header
    partial owns the site ``<nav>`` (issue 14), so a page is exactly
    ``<header><nav>…</nav></header>`` + the normalized ``<main>`` body +
    ``<footer>`` — no separate nav, and (because stage-3 bodies are normalized)
    no chrome inside ``<main>``.
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=1280">\n'
        f"<title>{title}</title>\n"
        f'<link rel="stylesheet" href="{VARIABLES_CSS}">\n'
        f'<link rel="stylesheet" href="{COMPONENTS_CSS}">\n'
        "</head>\n"
        "<body>\n"
        f"{design.header_html}\n"
        f"{body}\n"
        f"{design.footer_html}\n"
        "</body>\n"
        "</html>\n"
    )
