"""Behavioral tests for stage-3 body normalization (chrome stripping).

Stage 3 is asked for only the ``<main>…</main>`` section content, but the live
model sometimes adds a full ``<header><nav>…</nav></header>`` and ``<footer>``
*inside* the body (even nested inside ``<main>``), with placeholder ``#`` links —
inconsistently per page. The orchestrator then injects the real chrome on top, so
the page renders with duplicate, per-page-inconsistent chrome and the
chrome-identity gate fails unrepairably.

Normalization makes that impossible by construction: before assembly, every
``<header>``/``<nav>``/``<footer>`` (at any nesting depth) is stripped and the
remaining section content is wrapped in exactly one ``<main>``. These tests pin
that behavior through the public :func:`normalize_stage3_body` helper.
"""

import re

from webdesign_rl.generate import stages
from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.quality_gate import _resolves
from webdesign_rl.generate.stages import DesignSystem, Spec, normalize_stage3_body
from webdesign_rl.generate.slug import derive_page_map


def _count(tag, html):
    return len(re.findall(rf"<{tag}\b", html, re.IGNORECASE))


def test_strips_chrome_nested_inside_main():
    # The live failure: a bogus header/nav/footer nested *inside* <main>.
    raw = (
        '<main class="page">'
        '<header class="x"><nav><a href="#">Home</a></nav></header>'
        '<section class="hero"><h1>Welcome</h1><p>Real content here.</p></section>'
        '<footer class="y"><p>(c) 2026</p></footer>'
        "</main>"
    )
    out = normalize_stage3_body(raw)
    assert _count("header", out) == 0
    assert _count("nav", out) == 0
    assert _count("footer", out) == 0
    # The genuine section content survives.
    assert "Welcome" in out and "Real content here." in out
    # Exactly one <main> wrapper remains.
    assert _count("main", out) == 1


def test_strips_top_level_chrome_siblings_and_wraps_in_main():
    # Stage 3 returned a full page wrapper: header + main + footer as siblings.
    raw = (
        '<header class="site-header"><nav><a href="#">Home</a></nav></header>'
        '<main class="page"><section class="hero"><h1>Hi</h1></section></main>'
        '<footer class="site-footer">(c)</footer>'
    )
    out = normalize_stage3_body(raw)
    assert _count("header", out) == 0
    assert _count("nav", out) == 0
    assert _count("footer", out) == 0
    # The existing <main> is kept (not double-wrapped).
    assert _count("main", out) == 1
    assert "Hi" in out


def test_wraps_bare_section_content_with_no_main():
    # No <main> at all — the remaining content must be wrapped in exactly one.
    raw = '<section class="hero"><h1>Welcome</h1><p>Body copy.</p></section>'
    out = normalize_stage3_body(raw)
    assert _count("main", out) == 1
    assert out.startswith("<main")
    assert out.endswith("</main>")
    assert "Welcome" in out and "Body copy." in out


def test_already_clean_main_is_preserved():
    # A correctly-formed stage-3 body passes through unchanged in substance.
    raw = (
        '<main class="page"><section class="hero"><h1>Title</h1>'
        "<p>Paragraph with content.</p></section></main>"
    )
    out = normalize_stage3_body(raw)
    assert _count("main", out) == 1
    assert "Title" in out and "Paragraph with content." in out
    # Idempotent.
    assert normalize_stage3_body(out) == out


def _design():
    return DesignSystem(
        variables_css=":root{}",
        components_css=".hero{}",
        header_html='<header class="site-header"><nav>'
        '<a href="index.html">Home</a></nav></header>',
        footer_html='<footer class="site-footer">(c)</footer>',
    )


def _spec():
    page_map = derive_page_map(["Home"])
    slug = list(page_map)[0]
    return Spec(
        brief="b",
        pages=[{"slug": slug, "title": "Home", "sections": ["hero"]}],
        component_manifest=["hero"],
        page_map=page_map,
    )


def test_run_stage3_returns_normalized_chrome_free_body():
    # The model wrongly returns in-body chrome; run_stage3 must strip it.
    dirty = (
        '<main class="page">'
        '<header><nav><a href="#">Home</a></nav></header>'
        '<section class="hero"><h1>Welcome</h1></section>'
        "</main>"
    )
    client = StubGenerationClient(responses=[dirty])
    spec = _spec()
    body = stages.run_stage3(spec, _design(), spec.pages[0], client)
    assert _count("header", body) == 0
    assert _count("nav", body) == 0
    assert _count("main", body) == 1
    assert "Welcome" in body


# --- Sitemap-aware body-link normalization (issue 17) ----------------------


def _hrefs(html):
    return re.findall(r'<a\b[^>]*\bhref="([^"]*)"', html, re.IGNORECASE)


def test_internal_unresolvable_links_rewritten_to_hash():
    # The live failure: CTA buttons link to invented routes not in the sitemap.
    valid = {"index.html", "tickets.html", "venue.html"}
    raw = (
        '<main class="page">'
        '<a class="btn" href="/get-started">Get Started</a>'
        '<a class="btn" href="/register">Register</a>'
        "</main>"
    )
    out = normalize_stage3_body(raw, valid_pages=valid)
    assert _hrefs(out) == ["#", "#"]


def test_preserves_inert_and_real_page_links():
    valid = {"index.html", "tickets.html", "venue.html"}
    raw = (
        '<main class="page">'
        '<a href="https://example.com">External</a>'
        '<a href="//cdn.example.com/x">Protocol-relative</a>'
        '<a href="#section">Anchor</a>'
        '<a href="mailto:a@b.com">Mail</a>'
        '<a href="tel:+1">Call</a>'
        '<a href="tickets.html">Tickets</a>'
        '<a href="tickets.html#agenda">Agenda</a>'
        "</main>"
    )
    out = normalize_stage3_body(raw, valid_pages=valid)
    assert _hrefs(out) == [
        "https://example.com",
        "//cdn.example.com/x",
        "#section",
        "mailto:a@b.com",
        "tel:+1",
        "tickets.html",
        "tickets.html#agenda",
    ]


def test_chrome_strip_and_link_rewrite_compose():
    # A body with both nested chrome AND a bad link: chrome gone, link fixed,
    # wrapped in exactly one <main>.
    valid = {"index.html", "tickets.html"}
    raw = (
        '<header class="x"><nav><a href="/nav-route">Nav</a></nav></header>'
        '<section class="hero"><a href="/get-started">Go</a></section>'
        '<footer><a href="/footer-route">F</a></footer>'
    )
    out = normalize_stage3_body(raw, valid_pages=valid)
    assert _count("header", out) == 0
    assert _count("nav", out) == 0
    assert _count("footer", out) == 0
    assert _count("main", out) == 1
    # Only the surviving (in-body) link remains, rewritten to inert.
    assert _hrefs(out) == ["#"]


def test_no_valid_pages_means_no_link_rewriting():
    # Back-compat: omitting valid_pages preserves today's behavior (no rewrite).
    raw = '<main class="page"><a href="/get-started">Go</a></main>'
    assert _hrefs(normalize_stage3_body(raw)) == ["/get-started"]
    assert _hrefs(normalize_stage3_body(raw, valid_pages=None)) == ["/get-started"]


def test_run_stage3_yields_no_unresolvable_internal_links():
    # End-to-end: a stage-3 body of invented-route CTAs has every internal link
    # resolvable against the real sitemap filenames after run_stage3.
    page_map = derive_page_map(["Home", "Tickets", "Venue"])
    slugs = list(page_map)
    spec = Spec(
        brief="b",
        pages=[
            {"slug": slugs[0], "title": "Home", "sections": ["hero"]},
            {"slug": slugs[1], "title": "Tickets", "sections": ["hero"]},
            {"slug": slugs[2], "title": "Venue", "sections": ["hero"]},
        ],
        component_manifest=["hero"],
        page_map=page_map,
    )
    site_files = {f"{s}.html" for s in slugs}
    dirty = (
        '<main class="page">'
        '<section class="hero">'
        '<a href="/get-started">Get Started</a>'
        '<a href="/demo">Demo</a>'
        f'<a href="{slugs[1]}.html">Tickets</a>'
        "</section>"
        "</main>"
    )
    client = StubGenerationClient(responses=[dirty])
    body = stages.run_stage3(spec, _design(), spec.pages[0], client)
    for href in _hrefs(body):
        assert _resolves(href, site_files), href
