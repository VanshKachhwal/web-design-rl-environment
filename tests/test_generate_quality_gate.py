"""Behavioral tests for the stage-4 deterministic quality gate.

The gate answers "is this generated site a valid, faithfully-replicable target?"
purely from the written site files + the stage-1 ``spec`` — no live render, no
LLM. Each test builds a small fixture site on disk (mirroring the grader's
fixture-site approach) and asserts one check fires in isolation with a precise,
repair-ready diagnostic, plus a good fixture that passes everything.

The site directory shape is exactly what ``llm_site_generator.generate_site``
writes: ``variables.css`` + ``components.css``, one ``<slug>.html`` per page (a
full document linking only those two stylesheets and injecting byte-identical
header/nav/footer chrome), and ``page_map.json``.
"""

import json
from pathlib import Path

from webdesign_rl.generate.quality_gate import run_stage4_gate
from webdesign_rl.generate.stages import Spec
from webdesign_rl.generate.slug import derive_page_map


# --- Fixture-site builder ---------------------------------------------------
#
# A parameterizable good site we can perturb one axis at a time. Defaults
# produce a site that passes every stage-4 check; each test overrides exactly
# one thing to make exactly one check fail.

VARIABLES_CSS = (
    ":root{\n"
    "  --brand: #8a5a44;\n"
    "  --bg: #faf6f1;\n"
    "  --ink: #2b2b2b;\n"
    "  --space: 16px;\n"
    "  --radius: 8px;\n"
    "}\n"
)

COMPONENTS_CSS = (
    ".hero{ background: var(--bg); padding: var(--space); color: var(--ink); }\n"
    ".feature-grid{ display: grid; gap: var(--space); }\n"
    ".content-section{ padding: var(--space); }\n"
    ".card{ border-radius: var(--radius); background: var(--bg); }\n"
    ".contact-block{ padding: var(--space); }\n"
    ".btn{ background: var(--brand); border-radius: var(--radius);"
    " transition: background 0.2s; }\n"
    ".btn:hover{ background: var(--ink); }\n"
)

# The nav lives inside the header partial (issue 14); there is no separate nav.
NAV_HTML = (
    '<nav class="site-nav"><a href="index.html">Home</a>'
    '<a href="about.html">About</a></nav>'
)
HEADER_HTML = (
    f'<header class="site-header"><span>Cha Tea</span>{NAV_HTML}</header>'
)
FOOTER_HTML = '<footer class="site-footer"><p>(c) Cha Tea</p></footer>'

# A body using >=3 distinct catalog components (excl chrome) and >=50 words.
RICH_BODY = (
    '<main class="page">'
    '<section class="hero"><h1>Welcome</h1>'
    "<p>We are a boutique tea shop sourcing single-origin leaves from small "
    "family farms across the world. Every batch is roasted in small lots and "
    "tasted before it ever reaches your cup, so you always get something "
    "genuinely remarkable and fresh.</p></section>"
    '<section class="feature-grid"><div class="card"><h2>Loose Leaf</h2>'
    "<p>Hand-blended seasonal selections delivered to your door each month.</p>"
    "</div></section>"
    '<section class="contact-block"><h2>Visit Us</h2>'
    "<p>Open daily from morning until evening in the heart of the old town.</p>"
    "</section></main>"
)


def _document(body, *, header=HEADER_HTML, footer=FOOTER_HTML,
              head_extra="", title="Page"):
    # The header partial owns the site nav, so a page is header + body + footer
    # (no separate nav injection).
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        '<link rel="stylesheet" href="variables.css">\n'
        '<link rel="stylesheet" href="components.css">\n'
        f"{head_extra}"
        "</head>\n"
        "<body>\n"
        f"{header}\n{body}\n{footer}\n"
        "</body>\n"
        "</html>\n"
    )


_PAGE_TITLES = ["Home", "About", "Teas"]
_PAGE_SECTIONS = {
    "Home": ["hero", "feature-grid", "contact-block"],
    "About": ["hero", "content-section", "card"],
    "Teas": ["hero", "feature-grid", "card"],
}
_MANIFEST = ["hero", "feature-grid", "content-section", "card", "contact-block"]


def _spec():
    page_map = derive_page_map(_PAGE_TITLES)
    slugs = list(page_map)
    pages = [
        {"slug": slug, "title": title, "sections": list(_PAGE_SECTIONS[title])}
        for slug, title in zip(slugs, _PAGE_TITLES)
    ]
    return Spec(
        brief="A boutique tea shop.",
        pages=pages,
        component_manifest=list(_MANIFEST),
        page_map=page_map,
    )


def build_site(tmp_path, *, bodies=None, variables=VARIABLES_CSS,
               components=COMPONENTS_CSS, header_per_page=None,
               head_extra_per_page=None, omit_page=None, omit_file=None,
               extra_files=None) -> Path:
    """Write a good site to disk, with optional single-axis perturbations.

    Defaults produce a site that passes every stage-4 check. Each keyword lets a
    test break exactly one thing.
    """
    site = tmp_path / "site"
    site.mkdir(parents=True, exist_ok=True)
    spec = _spec()

    if variables is not None:
        (site / "variables.css").write_text(variables)
    if components is not None:
        (site / "components.css").write_text(components)

    bodies = bodies or {}
    head_extra_per_page = head_extra_per_page or {}
    header_per_page = header_per_page or {}

    for page in spec.pages:
        slug = page["slug"]
        if slug == omit_page:
            continue
        body = bodies.get(slug, RICH_BODY)
        header = header_per_page.get(slug, HEADER_HTML)
        head_extra = head_extra_per_page.get(slug, "")
        (site / f"{slug}.html").write_text(
            _document(body, header=header, head_extra=head_extra,
                      title=page["title"])
        )

    (site / "page_map.json").write_text(json.dumps(spec.page_map, indent=2))

    if omit_file is not None:
        (site / omit_file).unlink()
    for name, content in (extra_files or {}).items():
        (site / name).write_text(content)

    return site


def _messages(result):
    return " | ".join(d["message"] for d in result.diagnostics)


def _checks(result):
    return {d["check"] for d in result.diagnostics}


# --- Tracer bullet: the good fixture passes everything ----------------------

def test_good_fixture_passes_all_checks(tmp_path):
    site = build_site(tmp_path)
    result = run_stage4_gate(site, _spec())
    assert result.passed is True, _messages(result)
    assert result.diagnostics == []


# --- Token compliance -------------------------------------------------------

def test_structural_px_literals_in_components_css_pass(tmp_path):
    # The frozen design system legitimately contains structural literals
    # (border-radius, padding) and is shared byte-identically by every page, so
    # it cannot cause cross-page drift -> it is EXEMPT from the literal check.
    # Use literals that are NOT declared tokens (3px, 7px, #333333) to prove the
    # exemption, not mere coincidence with a token value.
    structural = COMPONENTS_CSS + (
        "\n.badge{ border-radius: 3px; padding: 7px; border: 1px solid #333333; }\n"
    )
    site = build_site(tmp_path, components=structural)
    result = run_stage4_gate(site, _spec())
    assert result.passed is True, _messages(result)


def test_literals_in_variables_css_pass(tmp_path):
    # variables.css is the single source of truth — its literals are the token
    # definitions and are likewise exempt.
    extra_tokens = VARIABLES_CSS.replace(
        "}\n", "  --hairline: 1px;\n  --shadow-color: #00000022;\n}\n"
    )
    site = build_site(tmp_path, variables=extra_tokens)
    result = run_stage4_gate(site, _spec())
    assert result.passed is True, _messages(result)


def test_off_token_px_in_page_inline_style_is_flagged(tmp_path):
    body = RICH_BODY.replace(
        '<main class="page">', '<main class="page" style="margin: 13px;">'
    )
    site = build_site(tmp_path, bodies={"index": body})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"token_compliance"}
    assert "13px" in _messages(result)
    # The failure is keyed to the page (repairable per-page), not site-wide.
    assert all(d["page"] == "index.html" for d in result.diagnostics)


def test_off_token_color_in_page_style_block_is_flagged(tmp_path):
    # A new color introduced in a page <style> block is real cross-page drift
    # and must fail, scoped to that page so the per-page nudge can repair it.
    head = "<style>.local{ color: #abcdef; }</style>\n"
    site = build_site(tmp_path, head_extra_per_page={"index": head})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"token_compliance"}
    assert "#abcdef" in _messages(result)
    assert all(d["page"] == "index.html" for d in result.diagnostics)


# --- Manifest compliance ----------------------------------------------------

def test_referenced_but_unstyled_component_is_flagged(tmp_path):
    # Spec references 'testimonial' (a legal catalog component) but
    # components.css styles no .testimonial rule.
    spec = _spec()
    spec.pages[1]["sections"].append("testimonial")
    site = build_site(tmp_path)
    result = run_stage4_gate(site, spec)
    assert result.passed is False
    assert _checks(result) == {"manifest_compliance"}
    assert "testimonial" in _messages(result)
    assert "not styled" in _messages(result)


def test_illegal_component_is_flagged(tmp_path):
    # 'carousel' is not in taxonomy.legal_components().
    spec = _spec()
    spec.pages[0]["sections"].append("carousel")
    site = build_site(tmp_path)
    result = run_stage4_gate(site, spec)
    assert result.passed is False
    assert _checks(result) == {"manifest_compliance"}
    assert "carousel" in _messages(result)
    assert "legal component catalog" in _messages(result)


# --- Hermeticity ------------------------------------------------------------

def test_external_font_link_is_flagged(tmp_path):
    head = '<link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Inter">\n'
    site = build_site(tmp_path, head_extra_per_page={"index": head})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"hermeticity"}
    assert "fonts.googleapis.com" in _messages(result)


def test_external_image_is_flagged(tmp_path):
    body = RICH_BODY.replace(
        "</main>", '<img src="https://cdn.example.com/photo.jpg" alt="x"></main>'
    )
    site = build_site(tmp_path, bodies={"index": body})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"hermeticity"}
    assert "cdn.example.com" in _messages(result)


def test_external_script_is_flagged(tmp_path):
    # An external script trips BOTH hermeticity and static-only (it is genuinely
    # both an external load and a script) — assert hermeticity reports it.
    head = '<script src="https://cdn.example.com/a.js"></script>\n'
    site = build_site(tmp_path, head_extra_per_page={"index": head})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert "hermeticity" in _checks(result)
    assert "cdn.example.com" in _messages(result)


def test_external_font_face_url_in_css_is_flagged(tmp_path):
    bad = VARIABLES_CSS + (
        '@font-face{ font-family: X; src: url(https://x.com/f.woff2); }\n'
    )
    site = build_site(tmp_path, variables=bad)
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"hermeticity"}
    assert "x.com/f.woff2" in _messages(result)


def test_external_anchor_hyperlink_passes(tmp_path):
    # An inert external <a href=http> is realistic and never fetched -> allowed.
    body = RICH_BODY.replace(
        "</main>", '<a href="https://twitter.com/chatea">Follow us</a></main>'
    )
    site = build_site(tmp_path, bodies={"index": body})
    result = run_stage4_gate(site, _spec())
    assert result.passed is True, _messages(result)


def test_broken_internal_link_is_flagged(tmp_path):
    body = RICH_BODY.replace(
        "</main>", '<a href="nonexistent.html">Ghost</a></main>'
    )
    site = build_site(tmp_path, bodies={"index": body})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"hermeticity"}
    assert "nonexistent.html" in _messages(result)


def test_route_style_and_hallucinated_chrome_links_fail_hermeticity(tmp_path):
    # Regression for the first live run: stage 2 authored web-style routes
    # (href="/features", href="/") and links to pages it invented (/login) in
    # the byte-identical chrome. None of those resolve to a bundled <slug>.html,
    # so the hermeticity "internal refs must resolve" check must fail them.
    bad_nav = (
        '<nav class="site-nav">'
        '<a href="/">Home</a>'
        '<a href="/features">Features</a>'
        '<a href="/login">Log in</a>'
        "</nav>"
    )
    site = build_site(tmp_path, header_per_page=None)
    # Rewrite every page's nav to the broken chrome (chrome stays identical, so
    # only hermeticity — not chrome_identity — should fire).
    for html in site.glob("*.html"):
        html.write_text(
            html.read_text().replace(NAV_HTML, bad_nav)
        )
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"hermeticity"}
    msg = _messages(result)
    assert "/features" in msg and "/login" in msg
    assert "does not resolve" in msg


# --- Static-only ------------------------------------------------------------

def test_inline_script_is_flagged(tmp_path):
    head = "<script>console.log('hi');</script>\n"
    site = build_site(tmp_path, head_extra_per_page={"index": head})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"static_only"}
    assert "<script>" in _messages(result) or "script" in _messages(result)


def test_keyframes_is_flagged(tmp_path):
    bad = COMPONENTS_CSS + "\n@keyframes spin{ from{} to{} }\n"
    site = build_site(tmp_path, components=bad)
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"static_only"}
    assert "@keyframes" in _messages(result)


def test_animation_property_is_flagged(tmp_path):
    bad = COMPONENTS_CSS + "\n.hero{ animation: spin 2s linear infinite; }\n"
    site = build_site(tmp_path, components=bad)
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"static_only"}
    assert "animation" in _messages(result)


def test_interaction_reveal_rule_is_flagged(tmp_path):
    # Content hidden until :hover toggles its display -> cannot survive a static
    # capture.
    bad = COMPONENTS_CSS + (
        "\n.faq-answer{ display: none; }\n"
        ".faq:hover .faq-answer{ display: block; }\n"
    )
    site = build_site(tmp_path, components=bad)
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"static_only"}
    assert "hover" in _messages(result)


def test_transition_and_cosmetic_hover_pass(tmp_path):
    # transition + a :hover that only changes color/background is cosmetic -> ok.
    # (The good fixture already includes .btn:hover{ background: var(--ink); }.)
    ok = COMPONENTS_CSS + "\n.card:hover{ color: var(--brand); }\n"
    site = build_site(tmp_path, components=ok)
    result = run_stage4_gate(site, _spec())
    assert result.passed is True, _messages(result)


# --- Completeness -----------------------------------------------------------

def test_missing_page_fails_completeness(tmp_path):
    spec = _spec()
    missing_slug = spec.pages[1]["slug"]
    site = build_site(tmp_path, omit_page=missing_slug)
    result = run_stage4_gate(site, spec)
    assert result.passed is False
    assert "completeness" in _checks(result)
    assert f"{missing_slug}.html" in _messages(result)


def test_missing_shared_stylesheet_fails_completeness(tmp_path):
    site = build_site(tmp_path, omit_file="components.css")
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert "completeness" in _checks(result)
    assert "components.css" in _messages(result)


# --- Target identity --------------------------------------------------------

def test_missing_page_map_fails_target_identity(tmp_path):
    site = build_site(tmp_path, omit_file="page_map.json")
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert "target_identity" in _checks(result)
    assert "page_map.json" in _messages(result)


def test_mismatched_page_map_entry_fails_target_identity(tmp_path):
    spec = _spec()
    site = build_site(tmp_path)
    # Corrupt one entry so it no longer derives 1:1 from the slug.
    bad_map = dict(spec.page_map)
    first = next(iter(bad_map))
    bad_map[first] = {"screenshot": "wrong.png", "expected_file": "wrong.html"}
    (site / "page_map.json").write_text(json.dumps(bad_map))
    result = run_stage4_gate(site, spec)
    assert result.passed is False
    assert "target_identity" in _checks(result)
    assert first in _messages(result)


# --- Per-page substance -----------------------------------------------------

def test_near_empty_page_fails_substance(tmp_path):
    thin = '<main class="page"><section class="hero"><h1>Hi</h1></section></main>'
    site = build_site(tmp_path, bodies={"index": thin})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"substance"}
    msg = _messages(result)
    assert "index.html" in msg


def test_too_few_distinct_components_fails_substance(tmp_path):
    # Plenty of words, but only ONE distinct catalog component (hero).
    one_component = (
        '<main class="page"><section class="hero"><h1>Welcome</h1>'
        "<p>We are a boutique tea shop sourcing single-origin leaves from small "
        "family farms across the world. Every batch is roasted in small lots and "
        "tasted before it ever reaches your cup, so you always get something "
        "genuinely remarkable, fresh, and worth the journey to find it.</p>"
        "</section></main>"
    )
    site = build_site(tmp_path, bodies={"index": one_component})
    result = run_stage4_gate(site, _spec())
    assert result.passed is False
    assert _checks(result) == {"substance"}
    assert "distinct catalog component" in _messages(result)


# --- Chrome identity --------------------------------------------------------

def test_differing_chrome_fails_chrome_identity(tmp_path):
    other_header = '<header class="site-header"><span>DIFFERENT</span></header>'
    spec = _spec()
    drift_slug = spec.pages[1]["slug"]
    site = build_site(tmp_path, header_per_page={drift_slug: other_header})
    result = run_stage4_gate(site, spec)
    assert result.passed is False
    assert _checks(result) == {"chrome_identity"}
    assert "header" in _messages(result)
