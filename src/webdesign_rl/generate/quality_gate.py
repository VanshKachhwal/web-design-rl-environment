"""Stage-4 deterministic quality gate — is this a valid, replicable target?

The gate consumes only the **written site files + the stage-1 ``spec``** and runs
a fixed battery of deterministic checks (no live render, no LLM). It returns a
:class:`GateResult` whose ``diagnostics`` are precise and *repair-ready*: each one
names the failing ``check``, the ``page`` or file it occurred on, and a message
specific enough to feed verbatim back to the stage-3 nudge loop (issue 04), e.g.
``"pricing.html: .hero uses color #333 (not a token); use only var(--…)"``.

The checks (each operates on the DOM/CSS text + the spec):

- **completeness** — every spec page has a ``<slug>.html``; the shared stylesheets
  exist; HTML/CSS parse; internal links resolve.
- **target_identity** — ``page_map.json`` is present and maps each spec page 1:1
  to its expected ``<slug>.html`` / ``<slug>.png``.
- **substance** — each page uses >=3 distinct catalog components (excl. chrome)
  AND has >=50 words of real DOM text. (The rendered-height bound is deferred to
  the stage-5 render gate — see issue 04.)
- **token_compliance** — no hex/rgb/raw-px value outside ``variables.css`` lives in
  ``components.css`` or page CSS; everything must trace to a ``var(--…)`` token.
- **manifest_compliance** — every section a page references is within
  :func:`taxonomy.legal_components` AND has a rule styled in ``components.css``.
- **chrome_identity** — header/nav/footer byte-identical across pages.
- **hermeticity** — no external resource loads (``<link>``/``<script>``/``<img
  src=http>``/``@import``/``@font-face url(http)``/css ``url(http)``) -> fail;
  internal refs must resolve; external ``<a href=http>`` is allowed (inert).
- **static_only** — fail on any ``<script>``, ``@keyframes``/``animation:``, or
  interaction-*reveal* rule (``:hover/:focus/:target/:checked`` toggling
  ``display``/``visibility``/``opacity``/``max-height`` of content); allow
  ``transition`` + cosmetic hover; disclosure components must render open.
"""

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from . import taxonomy

VARIABLES_CSS = "variables.css"
COMPONENTS_CSS = "components.css"

# Components that are chrome, not page substance — excluded from the per-page
# distinct-component count (the substance floor counts sections only).
_CHROME = frozenset(taxonomy.CHROME_COMPONENTS)

_MIN_DISTINCT_COMPONENTS = 3
_MIN_WORDS = 50


@dataclass(frozen=True)
class GateResult:
    """Outcome of the stage-4 gate.

    ``passed`` is ``True`` iff ``diagnostics`` is empty. Each diagnostic is a
    ``{"check", "page", "message"}`` dict (``page`` names the HTML file or shared
    file the problem is on, or ``None`` for site-wide checks).
    """

    passed: bool
    diagnostics: list = field(default_factory=list)


def _diag(check, page, message):
    return {"check": check, "page": page, "message": message}


# --- A tiny tolerant HTML reader -------------------------------------------
#
# We only need: tag names + attributes (for resource/link/script discovery),
# the set of class names used (for component detection), and the visible text
# (for the word count). stdlib ``html.parser`` is enough — no new dependency.


class _Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []           # (tagname, {attrs}) for every start/startend tag
        self.classes = set()     # every class token used anywhere
        self._text_parts = []
        self._suppress = 0       # depth inside <script>/<style> (not real text)
        self.has_script = False

    def handle_starttag(self, tag, attrs):
        attrs = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, attrs))
        if "class" in attrs:
            self.classes.update(attrs["class"].split())
        if tag == "script":
            self.has_script = True
            self._suppress += 1
        elif tag == "style":
            self._suppress += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._suppress:
            self._suppress -= 1

    def handle_data(self, data):
        if not self._suppress:
            self._text_parts.append(data)

    def text(self):
        return " ".join(self._text_parts)


def _parse_html(text):
    doc = _Doc()
    doc.feed(text)
    return doc


# --- CSS value scanning -----------------------------------------------------

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB = re.compile(r"\brgba?\([^)]*\)")
# A px length used as a property *value* (not inside a var() name or comment).
_PX = re.compile(r"(?<![\w-])\d*\.?\d+px\b")


def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _declared_token_block(variables_css):
    """The ``:root{…}`` token block text, where literal values legitimately live."""
    return _strip_comments(variables_css)


def _offending_values(css_without_comments):
    """Hex/rgb/raw-px literals appearing in a (comment-stripped) CSS string."""
    found = []
    found += _HEX.findall(css_without_comments)
    found += _RGB.findall(css_without_comments)
    found += _PX.findall(css_without_comments)
    return found


# --- External-resource detection -------------------------------------------

_EXTERNAL_URL = re.compile(r"https?://", re.IGNORECASE)
_PROTOCOL_RELATIVE = re.compile(r"""(?:src|href)\s*=\s*['"]//""", re.IGNORECASE)
_CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"@import\s+(?:url\()?\s*['\"]?([^'\");]+)", re.IGNORECASE)


def _is_external(url):
    return bool(_EXTERNAL_URL.match(url.strip()) or url.strip().startswith("//"))


# --- Static-only detection --------------------------------------------------

_REVEAL_SELECTOR = re.compile(r":(hover|focus|target|checked)")
_REVEAL_PROPS = ("display", "visibility", "opacity", "max-height")


def _css_rules(css):
    """Yield ``(selector, body)`` for each top-level rule in a CSS string.

    Good enough for the flat component CSS the generator emits (no nested
    at-rules beyond ``@media``/``@keyframes``, which we detect separately).
    """
    css = _strip_comments(css)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield match.group(1).strip(), match.group(2).strip()


# --- The checks -------------------------------------------------------------


def run_stage4_gate(site_dir, spec) -> GateResult:
    """Run every stage-4 check over ``site_dir`` given its stage-1 ``spec``.

    Returns a :class:`GateResult`; ``passed`` is true iff no check produced a
    diagnostic. Render-dependent checks (the substance floor's rendered-height
    bound, stage-5 validity) are intentionally NOT run here — they belong to the
    render gate in issue 04.
    """
    site_dir = Path(site_dir)
    diagnostics = []

    diagnostics += _check_completeness(site_dir, spec)
    diagnostics += _check_target_identity(site_dir, spec)
    diagnostics += _check_substance(site_dir, spec)
    diagnostics += _check_token_compliance(site_dir, spec)
    diagnostics += _check_manifest_compliance(site_dir, spec)
    diagnostics += _check_chrome_identity(site_dir, spec)
    diagnostics += _check_hermeticity(site_dir, spec)
    diagnostics += _check_static_only(site_dir, spec)

    return GateResult(passed=not diagnostics, diagnostics=diagnostics)


def _page_files(site_dir, spec):
    """Yield ``(slug, path, text)`` for each spec page that exists on disk."""
    for page in spec.pages:
        path = site_dir / f"{page['slug']}.html"
        if path.exists():
            yield page["slug"], path, path.read_text()


def _check_completeness(site_dir, spec):
    diagnostics = []
    for shared in (VARIABLES_CSS, COMPONENTS_CSS):
        if not (site_dir / shared).exists():
            diagnostics.append(_diag(
                "completeness", shared,
                f"shared file {shared} is missing from the site bundle",
            ))
    for page in spec.pages:
        name = f"{page['slug']}.html"
        if not (site_dir / name).exists():
            diagnostics.append(_diag(
                "completeness", name,
                f"spec page '{page['title']}' has no generated file {name}",
            ))
    return diagnostics


def _check_target_identity(site_dir, spec):
    diagnostics = []
    page_map_path = site_dir / "page_map.json"
    if not page_map_path.exists():
        diagnostics.append(_diag(
            "target_identity", "page_map.json",
            "page_map.json is missing; the agent<->reference pairing is undefined",
        ))
        return diagnostics
    try:
        page_map = json.loads(page_map_path.read_text())
    except json.JSONDecodeError as exc:
        diagnostics.append(_diag(
            "target_identity", "page_map.json",
            f"page_map.json does not parse as JSON: {exc}",
        ))
        return diagnostics

    spec_slugs = [page["slug"] for page in spec.pages]
    for slug in spec_slugs:
        if slug not in page_map:
            diagnostics.append(_diag(
                "target_identity", "page_map.json",
                f"spec page '{slug}' has no entry in page_map.json",
            ))
            continue
        entry = page_map[slug]
        expected = {"screenshot": f"{slug}.png", "expected_file": f"{slug}.html"}
        if entry != expected:
            diagnostics.append(_diag(
                "target_identity", "page_map.json",
                f"page_map['{slug}'] is {entry!r}; expected {expected!r} "
                "(filenames must derive 1:1 from the slug)",
            ))
    for slug in page_map:
        if slug not in spec_slugs:
            diagnostics.append(_diag(
                "target_identity", "page_map.json",
                f"page_map has stray slug '{slug}' not in the spec sitemap",
            ))
    return diagnostics


def _check_substance(site_dir, spec):
    diagnostics = []
    legal = taxonomy.legal_components()
    for slug, path, text in _page_files(site_dir, spec):
        doc = _parse_html(text)
        components = {c for c in doc.classes if c in legal and c not in _CHROME}
        if len(components) < _MIN_DISTINCT_COMPONENTS:
            diagnostics.append(_diag(
                "substance", path.name,
                f"{path.name}: only {len(components)} distinct catalog "
                f"component(s) {sorted(components)} (excl. chrome); need "
                f">={_MIN_DISTINCT_COMPONENTS}",
            ))
        words = len(doc.text().split())
        if words < _MIN_WORDS:
            diagnostics.append(_diag(
                "substance", path.name,
                f"{path.name}: only {words} words of real text; "
                f"need >={_MIN_WORDS}",
            ))
    return diagnostics


def _check_token_compliance(site_dir, spec):
    diagnostics = []
    declared = ""
    if (site_dir / VARIABLES_CSS).exists():
        declared = _declared_token_block((site_dir / VARIABLES_CSS).read_text())

    # The literal values that legitimately appear (they are the token defs).
    allowed = set(_offending_values(declared))

    def scan(label, css):
        for value in _offending_values(_strip_comments(css)):
            if value in allowed:
                continue
            diagnostics.append(_diag(
                "token_compliance", label,
                f"{label}: literal value {value} is not a token; use only "
                "var(--…) declared in variables.css",
            ))

    if (site_dir / COMPONENTS_CSS).exists():
        scan(COMPONENTS_CSS, (site_dir / COMPONENTS_CSS).read_text())

    for slug, path, text in _page_files(site_dir, spec):
        # Page-level CSS lives in <style> blocks and inline style="" attrs.
        for style_block in re.findall(r"<style[^>]*>(.*?)</style>", text,
                                      re.DOTALL | re.IGNORECASE):
            scan(path.name, style_block)
        for inline in re.findall(r'style\s*=\s*"([^"]*)"', text, re.IGNORECASE):
            scan(path.name, inline)
    return diagnostics


def _check_manifest_compliance(site_dir, spec):
    diagnostics = []
    legal = taxonomy.legal_components()

    components_css = ""
    if (site_dir / COMPONENTS_CSS).exists():
        components_css = (site_dir / COMPONENTS_CSS).read_text()
    styled = _styled_classes(components_css)

    for page in spec.pages:
        for section in page.get("sections", []):
            if section not in legal:
                diagnostics.append(_diag(
                    "manifest_compliance", f"{page['slug']}.html",
                    f"{page['slug']}.html references component '{section}' which "
                    "is not in the legal component catalog",
                ))
            elif section not in styled:
                diagnostics.append(_diag(
                    "manifest_compliance", f"{page['slug']}.html",
                    f"{page['slug']}.html references component '{section}' which "
                    "is not styled in components.css",
                ))
    return diagnostics


def _styled_classes(components_css):
    """Class names that have a rule in ``components.css`` (``.name{…}``)."""
    classes = set()
    for selector, _body in _css_rules(components_css):
        for match in re.finditer(r"\.([A-Za-z0-9_-]+)", selector):
            classes.add(match.group(1))
    return classes


def _extract_chrome(text):
    """The header/nav/footer triple (first of each) for chrome-identity compare."""
    def first(tag):
        match = re.search(rf"<{tag}\b.*?</{tag}>", text, re.DOTALL | re.IGNORECASE)
        return match.group(0) if match else None

    return (first("header"), first("nav"), first("footer"))


def _check_chrome_identity(site_dir, spec):
    diagnostics = []
    pages = list(_page_files(site_dir, spec))
    if len(pages) < 2:
        return diagnostics
    base_slug, _base_path, base_text = pages[0]
    base_chrome = _extract_chrome(base_text)
    for slug, path, text in pages[1:]:
        chrome = _extract_chrome(text)
        for label, base_block, block in zip(("header", "nav", "footer"),
                                             base_chrome, chrome):
            if block != base_block:
                diagnostics.append(_diag(
                    "chrome_identity", path.name,
                    f"{path.name}: {label} differs from {base_slug}.html; chrome "
                    "must be byte-identical across pages",
                ))
    return diagnostics


def _check_hermeticity(site_dir, spec):
    diagnostics = []

    def scan_css(label, css):
        css = _strip_comments(css)
        for url in _CSS_URL.findall(css):
            if _is_external(url):
                diagnostics.append(_diag(
                    "hermeticity", label,
                    f"{label}: external resource url({url}); bundle it locally or "
                    "use a CSS-drawable equivalent",
                ))
        for url in _CSS_IMPORT.findall(css):
            if _is_external(url):
                diagnostics.append(_diag(
                    "hermeticity", label,
                    f"{label}: external @import {url}; inline it locally",
                ))

    if (site_dir / VARIABLES_CSS).exists():
        scan_css(VARIABLES_CSS, (site_dir / VARIABLES_CSS).read_text())
    if (site_dir / COMPONENTS_CSS).exists():
        scan_css(COMPONENTS_CSS, (site_dir / COMPONENTS_CSS).read_text())

    site_files = {p.name for p in site_dir.iterdir() if p.is_file()}

    for slug, path, text in _page_files(site_dir, spec):
        doc = _parse_html(text)
        for tag, attrs in doc.tags:
            # External resource loads on link/script/img -> fail.
            if tag == "link":
                href = attrs.get("href", "")
                if _is_external(href):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: external <link href={href}>; the offline "
                        "render cannot fetch it",
                    ))
                elif href and not _resolves(href, site_files):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: <link href={href}> does not resolve to a "
                        "bundled file",
                    ))
            elif tag == "script":
                src = attrs.get("src", "")
                if _is_external(src):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: external <script src={src}>",
                    ))
            elif tag == "img":
                src = attrs.get("src", "")
                if _is_external(src):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: external <img src={src}>; use a "
                        "CSS-drawable / inline-SVG placeholder",
                    ))
                elif src and not _resolves(src, site_files):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: <img src={src}> does not resolve to a "
                        "bundled file",
                    ))
            elif tag == "a":
                # External hyperlinks are allowed (inert) — internal must resolve.
                href = attrs.get("href", "")
                if href and not _is_external(href) and not _resolves(href, site_files):
                    diagnostics.append(_diag(
                        "hermeticity", path.name,
                        f"{path.name}: internal link href={href} does not resolve "
                        "to a bundled file",
                    ))
        # @font-face / url() inside <style> blocks.
        for style_block in re.findall(r"<style[^>]*>(.*?)</style>", text,
                                      re.DOTALL | re.IGNORECASE):
            scan_css(path.name, style_block)
    return diagnostics


def _resolves(ref, site_files):
    """Whether an internal href/src resolves to a bundled file.

    Pure ``#anchor`` fragments and ``mailto:``/``tel:`` are not file refs and
    always 'resolve'. Otherwise the path's filename (minus query/fragment) must
    be a file in the bundle.
    """
    ref = ref.strip()
    if not ref or ref.startswith("#") or ref.startswith("mailto:") \
            or ref.startswith("tel:"):
        return True
    path = ref.split("#", 1)[0].split("?", 1)[0]
    if not path:
        return True
    name = path.rsplit("/", 1)[-1]
    return name in site_files


def _check_static_only(site_dir, spec):
    diagnostics = []

    def scan_css(label, css):
        stripped = _strip_comments(css)
        if re.search(r"@(-\w+-)?keyframes\b", stripped, re.IGNORECASE):
            diagnostics.append(_diag(
                "static_only", label,
                f"{label}: @keyframes is forbidden (no animation in a static "
                "Part-1 site)",
            ))
        for selector, body in _css_rules(stripped):
            # animation: shorthand/longhand (but not animation- inside transition).
            if re.search(r"(?<![\w-])animation(-\w+)?\s*:", body, re.IGNORECASE):
                diagnostics.append(_diag(
                    "static_only", label,
                    f"{label}: rule '{selector.strip()}' uses animation:; only "
                    "transition + cosmetic hover are allowed",
                ))
            # Interaction-reveal: a :hover/:focus/:target/:checked rule toggling a
            # content-reveal property is forbidden; cosmetic hover (color, bg,
            # transform) is fine.
            if _REVEAL_SELECTOR.search(selector):
                for prop in _REVEAL_PROPS:
                    if re.search(rf"(?<![\w-]){prop}\s*:", body, re.IGNORECASE):
                        diagnostics.append(_diag(
                            "static_only", label,
                            f"{label}: rule '{selector.strip()}' toggles {prop} on "
                            "interaction; content revealed only on "
                            "hover/focus/target/checked cannot survive a static "
                            "capture",
                        ))

    if (site_dir / COMPONENTS_CSS).exists():
        scan_css(COMPONENTS_CSS, (site_dir / COMPONENTS_CSS).read_text())
    if (site_dir / VARIABLES_CSS).exists():
        scan_css(VARIABLES_CSS, (site_dir / VARIABLES_CSS).read_text())

    for slug, path, text in _page_files(site_dir, spec):
        doc = _parse_html(text)
        if doc.has_script:
            diagnostics.append(_diag(
                "static_only", path.name,
                f"{path.name}: contains a <script> tag; the site must be static",
            ))
        for style_block in re.findall(r"<style[^>]*>(.*?)</style>", text,
                                      re.DOTALL | re.IGNORECASE):
            scan_css(path.name, style_block)
    return diagnostics
