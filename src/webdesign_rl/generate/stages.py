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
  Produces ``variables.css`` + ``components.css`` + the header (with the site
  nav authored inside it) and footer partials, authored as real CSS/HTML so
  consistency is enforced by shared artifacts, not prose.
- **Stage 3 (per page).** One call per page (temp 0.6, fanned out by the
  orchestrator). Each composes the frozen artifacts into the page's body markup,
  referencing only declared tokens/classes.
"""

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from . import fonts, slug as slug_mod

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
    """Stage-2 output: the frozen design-system artifacts pages bind to.

    Chrome is just **header + footer**: the header partial *owns* the
    sitemap-aware ``<nav>`` (authored inside it), so there is no separate nav
    artifact (issue 14). A standard page is therefore
    ``<header><nav>…</nav></header> … <footer>``.
    """

    variables_css: str
    components_css: str
    header_html: str
    footer_html: str


def _extract_json(text: str) -> dict:
    """Pull the first ``{...}`` JSON object out of a model response.

    Tolerant of code fences / surrounding prose, like the judge's parser.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("stage response contained no JSON object")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        # The most common cause is a response truncated mid-string (e.g. a large
        # components.css blob exceeding max_tokens), which leaves an unterminated
        # JSON string. Surface that explicitly instead of a bare decoder error.
        raise ValueError(
            f"stage response was not valid JSON ({exc}); the response is "
            f"{len(text)} chars and likely truncated (raise the client's "
            f"max_tokens or shrink the stage output). Tail: ...{text[-160:]!r}"
        ) from exc


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


# Stage 2 emits its four artifacts as escape-free ``===FILE <name>===`` blocks
# (not one JSON object), so large multi-line CSS never needs JSON escaping and a
# truncated response is a *missing block* (cleanly detectable) rather than an
# unterminated JSON string (a cryptic decoder crash). The file order in the
# response is irrelevant — blocks are looked up by name. The nav is authored
# *inside* the header block (issue 14), so there is no separate nav.html.
_STAGE2_FILES = (
    ("variables.css", "variables_css"),
    ("components.css", "components_css"),
    ("header.html", "header_html"),
    ("footer.html", "footer_html"),
)
_FILE_MARKER = re.compile(r"^===FILE[ \t]+(.+?)[ \t]*===[ \t]*$", re.MULTILINE)


def parse_design_system(text: str) -> DesignSystem:
    """Parse a delimited stage-2 response into a :class:`DesignSystem`.

    Splits on ``===FILE <name>===`` markers (tolerant of surrounding prose or
    code fences). A missing block — the signature of a response truncated before
    it finished — raises a clear :class:`ValueError` naming the missing file,
    rather than letting a downstream parser crash cryptically.
    """
    blocks = {}
    matches = list(_FILE_MARKER.finditer(text))
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        # Drop the single newline the marker line is terminated by, and any
        # trailing code-fence / whitespace, but preserve interior content.
        body = body.lstrip("\n")
        # For the final block, trailing prose/code-fence may follow the file
        # content; cut at the first closing fence line if one is present.
        body = re.split(r"\n```", body, maxsplit=1)[0]
        blocks[name] = body.rstrip("\n")

    fields = {}
    for filename, attr in _STAGE2_FILES:
        if filename not in blocks:
            raise ValueError(
                f"stage-2 response is missing the '{filename}' block; the "
                f"response is {len(text)} chars and likely truncated before it "
                f"finished (found blocks: {sorted(blocks)}). Tail: "
                f"...{text[-160:]!r}"
            )
        fields[attr] = blocks[filename]
    return DesignSystem(**fields)


def run_stage2(spec: Spec, client) -> DesignSystem:
    """Spec -> the frozen design system (variables/components CSS + partials)."""
    prompt = build_stage2_prompt(spec)
    raw = client.complete(prompt, temperature=STAGE2_TEMPERATURE)
    return parse_design_system(raw)


# Chrome tags stage 3 must never author — they come only from the injected
# stage-2 partials. Any of these in a stage-3 body (at any nesting depth) is
# stripped, so duplicate / per-page-inconsistent chrome is impossible by
# construction (issue 14).
_STRIP_TAGS = frozenset({"header", "nav", "footer"})
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
})


def _resolvable_href(href, valid_pages):
    """The href to serialize, rewriting an internal *unresolvable* link to ``#``.

    Mirrors :func:`quality_gate._resolves` exactly so a body link can never be a
    hermeticity defect: ``#fragment``, ``mailto:``/``tel:``, and external
    ``http(s)://`` / protocol-relative ``//`` links are inert/allowed and kept
    verbatim. For any other href the query/fragment is stripped and the final
    path segment (filename) must be one of the sitemap ``<slug>.html`` pages;
    otherwise the href is rewritten to ``#``.
    """
    stripped = href.strip()
    if (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("mailto:")
        or stripped.startswith("tel:")
        or stripped.startswith("//")
        or stripped.startswith("http://")
        or stripped.startswith("https://")
    ):
        return href
    path = stripped.split("#", 1)[0].split("?", 1)[0]
    name = path.rsplit("/", 1)[-1]
    if name in valid_pages:
        return href
    return "#"


class _BodyNormalizer(HTMLParser):
    """Re-serialize stage-3 markup with every header/nav/footer subtree dropped.

    The whole subtree of a stripped tag is omitted (a ``<header>`` containing a
    ``<nav>`` disappears entirely, including its text), so nested chrome — the
    live failure, where the model put a ``<header><nav>`` *inside* ``<main>`` —
    is removed. Everything else is reconstructed verbatim. A stdlib parser is
    used rather than regex because nested same-name tags defeat regex.

    When ``valid_pages`` is supplied, any ``<a href>`` on a surviving (in-body)
    link that is internal but does not resolve to one of those sitemap pages is
    rewritten to ``#`` (issue 17), so a broken internal link is impossible by
    construction — composing with the chrome strip in one pass.
    """

    def __init__(self, valid_pages=None):
        super().__init__(convert_charrefs=False)
        self._out = []
        self._skip_depth = 0  # >0 while inside a stripped chrome subtree
        self._valid_pages = valid_pages

    def _attrs_str(self, attrs):
        parts = []
        for key, value in attrs:
            if value is None:
                parts.append(f" {key}")
            else:
                parts.append(f' {key}="{value}"')
        return "".join(parts)

    def _rewrite_link_attrs(self, tag, attrs):
        """If link rewriting is on, coerce an ``<a>``'s href to a resolvable one."""
        if self._valid_pages is None or tag != "a":
            return attrs
        return [
            (key, _resolvable_href(value, self._valid_pages))
            if key == "href" and value is not None
            else (key, value)
            for key, value in attrs
        ]

    def handle_starttag(self, tag, attrs):
        if self._skip_depth or tag in _STRIP_TAGS:
            # Open (or already inside) a stripped subtree. Void chrome tags have
            # no end tag, so they must not bump the depth counter.
            if tag not in _VOID_TAGS:
                self._skip_depth += 1
            return
        attrs = self._rewrite_link_attrs(tag, attrs)
        self._out.append(f"<{tag}{self._attrs_str(attrs)}>")

    def handle_startendtag(self, tag, attrs):
        if self._skip_depth or tag in _STRIP_TAGS:
            return
        attrs = self._rewrite_link_attrs(tag, attrs)
        self._out.append(f"<{tag}{self._attrs_str(attrs)}/>")

    def handle_endtag(self, tag):
        if self._skip_depth:
            self._skip_depth -= 1
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self._skip_depth:
            self._out.append(data)

    def handle_entityref(self, name):
        if not self._skip_depth:
            self._out.append(f"&{name};")

    def handle_charref(self, name):
        if not self._skip_depth:
            self._out.append(f"&#{name};")

    def handle_comment(self, data):
        if not self._skip_depth:
            self._out.append(f"<!--{data}-->")

    def result(self):
        return "".join(self._out)


_MAIN_BLOCK = re.compile(r"<main\b[^>]*>.*</main>", re.DOTALL | re.IGNORECASE)


def normalize_stage3_body(raw: str, valid_pages=None) -> str:
    """Reduce stage-3 output to exactly one ``<main>`` of section content.

    Strips every ``<header>``/``<nav>``/``<footer>`` element at any nesting depth
    (chrome belongs only to the injected partials), then guarantees a single
    ``<main>`` wrapper: if the stripped markup already contains a ``<main>`` its
    content is kept as-is; otherwise the remaining content is wrapped in one.
    This makes duplicate / per-page-inconsistent chrome impossible by
    construction.

    When ``valid_pages`` (the set of sitemap ``<slug>.html`` filenames) is given,
    every surviving in-body ``<a href>`` that is internal but does not resolve to
    one of those pages is also rewritten to ``#`` (issue 17), mirroring the gate's
    hermeticity rule so a broken body link cannot occur. When it is ``None``
    (default) links are left untouched, preserving the prior behavior for
    unrelated callers.
    """
    parser = _BodyNormalizer(valid_pages=valid_pages)
    parser.feed(raw)
    parser.close()
    stripped = parser.result().strip()

    match = _MAIN_BLOCK.search(stripped)
    if match:
        return match.group(0).strip()
    return f'<main class="page">{stripped}</main>'


def run_stage3(spec: Spec, design: DesignSystem, page: dict, client) -> str:
    """One page's section list + frozen artifacts -> that page's body markup.

    The raw model output is **normalized** to section content only (chrome
    stripped, wrapped in exactly one ``<main>``, every internal link constrained
    to a real sitemap page) before it is returned, so the stage owns a clean
    output contract and the assembler can inject the frozen chrome without risking
    duplicates or broken internal links.
    """
    prompt = build_stage3_prompt(spec, design, page)
    raw = client.complete(prompt, temperature=STAGE3_TEMPERATURE)
    return normalize_stage3_body(raw, valid_pages=_valid_page_files(spec))


def _valid_page_files(spec: Spec) -> set:
    """The set of sitemap ``<slug>.html`` filenames a body link may point at.

    Derived from ``spec.pages`` (the ordered sitemap), which carries the same
    slugs as ``spec.page_map`` keys — the exact filenames the gate's hermeticity
    check resolves internal links against.
    """
    return {f"{page['slug']}.html" for page in spec.pages}


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


def _font_palette_clause() -> str:
    """The stage-2 typography constraint, derived from the fonts manifest.

    Pins ``font-family`` to the curated palette (named explicitly so the model
    uses the exact bare family names that resolve OS-level in the render image)
    and marks the display faces as headings-only. Sourced from the one manifest
    so the prompt, the image install, and the gate check never diverge.
    """
    text_families = ", ".join(
        f for f in fonts.PALETTE_FAMILIES if f not in fonts.HEADINGS_ONLY
    )
    display_families = ", ".join(sorted(fonts.HEADINGS_ONLY))
    return (
        "Typography: choose font-family values ONLY from this palette, by bare "
        f"family name (no @font-face, no web fonts). Text faces: {text_families}. "
        f"Display faces (headings only, never body text): {display_families}. "
        f"Always end each font-family stack with a generic fallback "
        f"(e.g. sans-serif / serif / monospace)."
    )


def _sitemap_lines(spec: Spec) -> str:
    """The page set as ``<slug>.html — Title`` lines for the stage-2 prompt."""
    return "\n".join(
        f"  {page['slug']}.html — {page['title']}" for page in spec.pages
    )


def build_stage2_prompt(spec: Spec) -> str:
    return (
        "Author the FROZEN design system for this site as real CSS and HTML "
        "partials. variables.css locks values (:root tokens for palette, type "
        "scale, spacing, radius). components.css locks structure for EXACTLY "
        f"these components: {json.dumps(spec.component_manifest)}. The header "
        "(which CONTAINS the site <nav>) and the footer partials are injected "
        "byte-identically into every page.\n"
        f"Brief: {spec.brief}\n"
        "The site's pages are EXACTLY these (relative filename — title):\n"
        f"{_sitemap_lines(spec)}\n"
        "Every nav / header / footer link MUST point at one of those exact "
        "relative filenames (the home page is index.html). Use relative "
        "filenames only — never web-style routes like \"/features\" or \"/\", and "
        "never link to a page not in this list (do NOT invent /login, /blog, "
        "/docs, /careers, etc.).\n"
        f"{_font_palette_clause()}\n"
        f"{_WELL_POSEDNESS}\n"
        "The header.html block MUST contain the site <nav> inside the <header> "
        "(do NOT emit a separate nav block).\n"
        "Respond with ONLY these four blocks, each introduced by its exact "
        "marker line, in this order, with the raw file contents in between (no "
        "JSON, no escaping, no code fences):\n"
        "===FILE variables.css===\n"
        "===FILE components.css===\n"
        "===FILE header.html===\n"
        "===FILE footer.html==="
    )


def build_stage3_prompt(spec: Spec, design: DesignSystem, page: dict) -> str:
    return (
        f"Compose the BODY markup for the '{page['title']}' page using ONLY the "
        "frozen design system below. Reference only declared component classes "
        "and var(--…) tokens — introduce no new color, size, or component.\n"
        f"Sections for this page: {json.dumps(page['sections'])}\n"
        f"variables.css:\n{design.variables_css}\n"
        f"components.css:\n{design.components_css}\n"
        "The site's pages are EXACTLY these (relative filename — title):\n"
        f"{_sitemap_lines(spec)}\n"
        "Every link in the body (CTA buttons, cards, inline links) MUST point at "
        "one of those exact relative filenames (the home page is index.html) or "
        "be inert (href=\"#\", a same-page #anchor, mailto:, or tel:). Route a CTA "
        "to the RIGHT real page (e.g. a \"Register\" / \"Get tickets\" button links "
        "to the relevant page in this list). Never invent a route like "
        "\"/get-started\", \"/demo\", or \"/register\", and never use web-style "
        "absolute paths like \"/\" or \"/features\".\n"
        f"{_WELL_POSEDNESS}\n"
        "Respond with ONLY the single <main>…</main> element holding this "
        "page's section content — no <html>, <head>, <header>, <nav>, "
        "<footer>, or any page wrapper (those are injected for you)."
    )
