"""The three generation stage runners — prompt assembly + response parsing.

Each stage builds a prompt, calls the LLM through the thin
:class:`~webdesign_rl.generate.client.GenerationClient`, and parses the response
into typed Python output. The nondeterminism (the model) lives behind the client
seam; everything here — prompt text, JSON extraction, the parsed dataclasses — is
deterministic and testable with a stub.

- **Stage 1 (seed -> spec).** One high-temperature (1.0) call. Produces the brief,
  the sitemap (page titles + per-page section list), and the deduplicated
  component manifest. The slugs / ``page_map`` are *derived in code* from the
  sitemap (``slug.derive_page_map``), not authored by the model.
- **Stage 2 (spec -> frozen design system).** One coherent call (temp 0.7).
  Produces ``variables.css`` + ``components.css`` + the header/nav/footer
  partials, authored as real CSS/HTML so consistency is enforced by shared
  artifacts, not prose.
- **Stage 3 (per page).** One call per page (temp 0.6, fanned out by the
  orchestrator). Each composes the frozen artifacts into the page's body markup,
  referencing only declared tokens/classes.
"""

import json
from dataclasses import dataclass

from . import slug as slug_mod

STAGE1_TEMPERATURE = 1.0
STAGE2_TEMPERATURE = 0.7
STAGE3_TEMPERATURE = 0.6


@dataclass(frozen=True)
class Spec:
    """Stage-1 output: the *what* of the site, frozen as identity for downstream.

    ``page_map`` is derived in code from the sitemap (one slug -> three
    derivations), so page identity is deterministic. ``pages`` preserves the
    sitemap order and pairs each slug with its section list.
    """

    brief: str
    pages: list  # ordered list of {"slug", "title", "sections"}
    component_manifest: list
    page_map: dict


@dataclass(frozen=True)
class DesignSystem:
    """Stage-2 output: the frozen design-system artifacts pages bind to."""

    variables_css: str
    components_css: str
    header_html: str
    nav_html: str
    footer_html: str


def _extract_json(text: str) -> dict:
    """Pull the first ``{...}`` JSON object out of a model response.

    Tolerant of code fences / surrounding prose, like the judge's parser.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("stage response contained no JSON object")
    return json.loads(text[start : end + 1])


def run_stage1(seed: dict, client) -> Spec:
    """Seed -> brief + sitemap + section lists + component manifest (+ page_map)."""
    prompt = build_stage1_prompt(seed)
    raw = client.complete(prompt, temperature=STAGE1_TEMPERATURE)
    data = _extract_json(raw)

    titles = [page["title"] for page in data["pages"]]
    page_map = slug_mod.derive_page_map(titles)
    slugs = list(page_map)

    pages = [
        {
            "slug": slug,
            "title": page["title"],
            "sections": list(page.get("sections", [])),
        }
        for slug, page in zip(slugs, data["pages"])
    ]
    return Spec(
        brief=data.get("brief", ""),
        pages=pages,
        component_manifest=list(data.get("component_manifest", [])),
        page_map=page_map,
    )


def run_stage2(spec: Spec, client) -> DesignSystem:
    """Spec -> the frozen design system (variables/components CSS + partials)."""
    prompt = build_stage2_prompt(spec)
    raw = client.complete(prompt, temperature=STAGE2_TEMPERATURE)
    data = _extract_json(raw)
    return DesignSystem(
        variables_css=data["variables_css"],
        components_css=data["components_css"],
        header_html=data["header_html"],
        nav_html=data["nav_html"],
        footer_html=data["footer_html"],
    )


def run_stage3(spec: Spec, design: DesignSystem, page: dict, client) -> str:
    """One page's section list + frozen artifacts -> that page's body markup."""
    prompt = build_stage3_prompt(spec, design, page)
    return client.complete(prompt, temperature=STAGE3_TEMPERATURE).strip()


# --- Prompt builders -------------------------------------------------------
#
# Kept deliberately compact and explicit; they encode the well-posedness rules
# (CSS-drawable only, hermetic, static, bare-family fonts) so a *real* run obeys
# them. Tests stub the client, so prompt wording is not asserted, but it is the
# load-bearing instruction set when wired to the live model.

_WELL_POSEDNESS = (
    "Hard constraints: the site must be STATIC (no <script>, no @keyframes or "
    "animation, no content revealed only on hover/focus/scroll) and HERMETIC "
    "(no external fonts/images/CSS/JS; no http(s):// resource URLs). All imagery "
    "must be CSS-drawable, solid-color blocks, or inline SVG patterns — no raster "
    "assets. Reference fonts by bare family name only."
)


def build_stage1_prompt(seed: dict) -> str:
    return (
        "You are designing a multi-page static website.\n"
        f"Seed (sample the design around this): {json.dumps(seed)}\n"
        "Produce a brief, a sitemap of 5-10 pages (the FIRST page is the home "
        "page), a per-page section list drawn from the canonical component "
        "catalog, and the deduplicated component manifest (the union of section "
        "types across pages).\n"
        f"{_WELL_POSEDNESS}\n"
        'Respond with ONLY a JSON object: {"brief": str, "pages": '
        '[{"title": str, "sections": [str]}], "component_manifest": [str]}.'
    )


def build_stage2_prompt(spec: Spec) -> str:
    return (
        "Author the FROZEN design system for this site as real CSS and HTML "
        "partials. variables.css locks values (:root tokens for palette, type "
        "scale, spacing, radius). components.css locks structure for EXACTLY "
        f"these components: {json.dumps(spec.component_manifest)}. The header, "
        "nav and footer partials are injected byte-identically into every page.\n"
        f"Brief: {spec.brief}\n"
        f"{_WELL_POSEDNESS}\n"
        'Respond with ONLY a JSON object: {"variables_css": str, '
        '"components_css": str, "header_html": str, "nav_html": str, '
        '"footer_html": str}.'
    )


def build_stage3_prompt(spec: Spec, design: DesignSystem, page: dict) -> str:
    return (
        f"Compose the BODY markup for the '{page['title']}' page using ONLY the "
        "frozen design system below. Reference only declared component classes "
        "and var(--…) tokens — introduce no new color, size, or component.\n"
        f"Sections for this page: {json.dumps(page['sections'])}\n"
        f"variables.css:\n{design.variables_css}\n"
        f"components.css:\n{design.components_css}\n"
        f"{_WELL_POSEDNESS}\n"
        "Respond with ONLY the <main>…</main> body markup (no <html>, <head>, "
        "header, nav, or footer — those are injected for you)."
    )
