"""Two-pass animated-site generation — trust the LLM, no structural enforcement.

Per the scaling decision, generation is two LLM passes (no component catalog, no
manifest/token gates — the model owns structure):

- **Pass 1 — plan + system** (one call): the model decides the brief and a 5-page
  sitemap (free-form page titles), and authors the shared system it will build
  against: ``styles.css`` + ``animations.css`` + a ``header`` (with nav) + ``footer``.
  Returned as labelled blocks: a ``===PLAN===`` JSON sitemap + four ``===FILE===``
  blocks. Slugs are derived in code from the sitemap (deterministic), home → index.

- **Pass 2 — build** (one call): given the plan + the shared system, the model emits
  the ``<main>`` body for every page as ``===FILE <slug>===`` blocks, applying the
  declared animation utility classes so every page animates on load.

Consistency comes from the *shared* stylesheets + chrome authored once in Pass 1 and
injected into every page (same idea as Task 1's frozen design system, minus the
rigid catalog). Bodies are cleaned with Task 1's ``normalize_stage3_body`` read-only.
The seed is a soft creative steer only (see ``seeds_anim``).
"""

import json
import re
from dataclasses import dataclass

from webdesign_rl.generate.stages import normalize_stage3_body  # reused read-only

# Plan authors CSS, so keep it focused (1.0 rambled into oversized stylesheets that
# overflowed the token cap). Build is per-page (small output) at a low temperature.
PLAN_TEMPERATURE = 0.7
BUILD_TEMPERATURE = 0.6


@dataclass(frozen=True)
class Plan:
    """Pass-1 output: the concept, the derived page set, and the shared system."""

    brief: str
    pages: list      # ordered [{"slug", "title"}]; home → index, first
    styles_css: str
    animations_css: str
    header_html: str
    footer_html: str

    @property
    def page_map(self) -> dict:
        return {
            p["slug"]: {"expected_file": f"{p['slug']}.html",
                        "screenshot": f"{p['slug']}.png"}
            for p in self.pages
        }


_ANIM_RULES = (
    "Animation MUST be CSS-only: @keyframes + CSS transitions. NO JavaScript, NO "
    "<script>, NO requestAnimationFrame (the grader seeks the CSS timeline and cannot "
    "see JS motion). Finite entrance/stagger animations MUST use animation-fill-mode: "
    "forwards so the page holds its end state at rest. Include at least one continuous "
    "(infinite) loop. Keep entrance + stagger within ~1800ms so motion shows early. "
    "Everything HERMETIC: inline/local only, system fonts, CSS-drawn shapes/gradients, "
    "no external fonts/images/CSS/JS, no http(s):// URLs (rendering is offline)."
)


def build_plan_prompt(steer: dict) -> str:
    n = steer.get("page_count", 5)
    return (
        f"Design a polished, real-looking **{n}-page animated website**. Use this as "
        f"loose creative direction (don't be literal, make it good and specific):\n"
        f"  site type: {steer.get('archetype')}\n"
        f"  aesthetic: {steer.get('aesthetic')}\n"
        f"  audience: {steer.get('audience')}\n"
        f"  brand mood: {steer.get('brand_mood')}\n"
        f"  motion character: {steer.get('animation_style')} — {steer.get('animation_style_hint')}\n\n"
        f"Decide the concept and an {n}-page sitemap (the FIRST page is the home page). "
        "Then author the SHARED design system every page will reuse: one styles.css "
        "(palette, type, layout, all component styling — you decide the components), "
        "one animations.css with @keyframes plus REUSABLE animation utility CLASSES "
        "(at minimum: an entrance class e.g. .anim-rise; a stagger mechanism e.g. "
        ".anim-delay-1..6 or .anim-stagger children; and at least one infinite loop "
        "class e.g. .anim-loop-pulse), and the header.html (containing the site <nav>) "
        "and footer.html partials injected byte-identically into every page.\n"
        "Keep the shared CSS focused and reasonably sized — a clean, coherent system, "
        "not an exhaustive utility framework.\n"
        f"{_ANIM_RULES}\n"
        "Every nav/header/footer link MUST point at a real page filename from your "
        'sitemap (home is index.html); relative filenames only, no "/" routes.\n'
        "Respond with EXACTLY these blocks in this order, raw contents between markers "
        "(no code fences):\n"
        '===PLAN===\n'
        '{"brief": "...", "pages": ["Home page title", "Second page title", ...]}\n'
        "===FILE styles.css===\n"
        "===FILE animations.css===\n"
        "===FILE header.html===\n"
        "===FILE footer.html==="
    )


def build_page_prompt(plan: Plan, page: dict) -> str:
    """Build ONE page's body (kept small per call so it never overflows the cap)."""
    sitemap = "\n".join(f"  {p['slug']}.html — {p['title']}" for p in plan.pages)
    return (
        f"Build the BODY of the '{page['title']}' page (file {page['slug']}.html) of "
        "this animated site, reusing ONLY the shared system below (reference its "
        "classes/tokens; do NOT introduce new @keyframes, colors, or a new design "
        "language).\n"
        f"Brief: {plan.brief}\n"
        f"All pages (relative filename — title):\n{sitemap}\n"
        f"styles.css:\n{plan.styles_css}\n"
        f"animations.css (APPLY these classes):\n{plan.animations_css}\n\n"
        "This page MUST visibly animate on load: put the entrance class on the hero / "
        "leading sections, apply the stagger mechanism to any card/list/grid group, "
        "and use a continuous-loop class on at least one accent element. Write real, "
        "specific content (no lorem ipsum).\n"
        f"{_ANIM_RULES}\n"
        "Every in-body link points at a real sitemap filename or is inert "
        '(href="#", #anchor, mailto:, tel:).\n'
        "Respond with ONLY the single <main>…</main> element for this page (no "
        "<html>/<head>/<header>/<nav>/<footer> or wrapper)."
    )


# --- parsing ----------------------------------------------------------------

_MARKER = re.compile(r"^===(?:FILE\s+)?(.+?)===\s*$")


def parse_blocks(raw: str) -> dict:
    """Split a ``===PLAN===`` / ``===FILE name===`` response into ``{label: body}``."""
    blocks, current, buf = {}, None, []
    for line in raw.splitlines():
        m = _MARKER.match(line.strip())
        if m:
            if current is not None:
                blocks[current] = "\n".join(buf).strip()
            current, buf = m.group(1).strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        blocks[current] = "\n".join(buf).strip()
    return blocks


def _slugify(title: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"
    slug, i = base, 2
    while slug in taken:
        slug, i = f"{base}-{i}", i + 1
    return slug


def _derive_pages(titles: list) -> list:
    """Map sitemap titles → ordered [{slug,title}]; the FIRST page is ``index``."""
    pages, taken = [], set()
    for i, title in enumerate(titles):
        title = str(title).strip() or f"Page {i+1}"
        slug = "index" if i == 0 else _slugify(title, taken)
        taken.add(slug)
        pages.append({"slug": slug, "title": title})
    return pages


class PlanError(ValueError):
    """Pass-1 output was unusable (no parseable plan / missing shared files)."""


def run_plan(steer: dict, client) -> Plan:
    raw = client.complete(build_plan_prompt(steer), temperature=PLAN_TEMPERATURE)
    b = parse_blocks(raw)
    plan_json = b.get("PLAN", "")
    start, end = plan_json.find("{"), plan_json.rfind("}")
    try:
        meta = json.loads(plan_json[start:end + 1]) if start != -1 else {}
    except (ValueError, TypeError):
        meta = {}
    titles = meta.get("pages") or []
    if len(titles) < 2:
        raise PlanError(f"plan sitemap had {len(titles)} page(s)")
    if not b.get("styles.css") or not b.get("animations.css"):
        raise PlanError("plan missing styles.css / animations.css")
    return Plan(
        brief=meta.get("brief", ""),
        pages=_derive_pages(titles),
        styles_css=b["styles.css"],
        animations_css=b["animations.css"],
        header_html=b.get("header.html", ""),
        footer_html=b.get("footer.html", ""),
    )


def run_build(plan: Plan, client) -> dict:
    """Pass 2 → ``{slug: normalized <main> body}``, one small call PER page.

    Per-page (not all-pages-in-one-call) so each response stays well under the token
    cap — the all-in-one variant overflowed and tripped the model's no-prefill
    continuation path. Pages still share one frozen system, so they stay coherent.
    """
    valid = {f"{p['slug']}.html" for p in plan.pages}
    bodies = {}
    for page in plan.pages:
        raw = client.complete(build_page_prompt(plan, page), temperature=BUILD_TEMPERATURE)
        bodies[page["slug"]] = normalize_stage3_body(raw, valid_pages=valid)
    return bodies


# --- assembly ---------------------------------------------------------------

STYLES_CSS = "styles.css"
ANIMATIONS_CSS = "animations.css"


def assemble_page(title: str, body: str, plan: Plan) -> str:
    """Full hermetic HTML doc: shared stylesheets + injected chrome + page body."""
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=1280">\n'
        f"<title>{title}</title>\n"
        f'<link rel="stylesheet" href="{STYLES_CSS}">\n'
        f'<link rel="stylesheet" href="{ANIMATIONS_CSS}">\n'
        "</head>\n<body>\n"
        f"{plan.header_html}\n{body}\n{plan.footer_html}\n"
        "</body>\n</html>\n"
    )
