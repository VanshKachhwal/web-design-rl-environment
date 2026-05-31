"""Behavioral tests for the escape-free delimited stage-2 output format.

Stage 2 emits the four frozen design-system artifacts (variables.css,
components.css, the header — which contains the site nav — and footer partials)
as ``===FILE <name>===`` delimited blocks rather than one JSON object, so large
multi-line CSS never has to be JSON-escaped and a truncated response is
detectable (a missing block) instead of crashing a JSON decoder on an
unterminated string.

These tests pin the round-trip parse and the missing-block / sitemap-aware
behavior through the public stage-2 surface (``parse_design_system``,
``build_stage2_prompt``, ``run_stage2``) with a stub client and no live call.
"""

import pytest

from webdesign_rl.generate import stages
from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.stages import (
    DesignSystem,
    Spec,
    build_stage2_prompt,
    parse_design_system,
    run_stage2,
)
from webdesign_rl.generate.slug import derive_page_map


def _spec():
    titles = ["Home", "Features", "Pricing", "About", "Contact"]
    page_map = derive_page_map(titles)
    slugs = list(page_map)
    pages = [
        {"slug": slug, "title": title, "sections": ["hero"]}
        for slug, title in zip(slugs, titles)
    ]
    return Spec(
        brief="A SaaS landing site.",
        pages=pages,
        component_manifest=["hero", "feature-grid", "pricing-table"],
        page_map=page_map,
    )


def _delimited(variables, components, header, footer):
    return (
        "===FILE variables.css===\n" + variables + "\n"
        "===FILE components.css===\n" + components + "\n"
        "===FILE header.html===\n" + header + "\n"
        "===FILE footer.html===\n" + footer + "\n"
    )


def test_parse_round_trips_the_four_artifacts():
    raw = _delimited(
        ":root{--brand:#8a5a44;}",
        ".hero{padding:16px;}\n.card{border-radius:8px;}",
        '<header class="site-header">X'
        '<nav class="site-nav"><a href="index.html">Home</a></nav></header>',
        '<footer class="site-footer">Y</footer>',
    )
    ds = parse_design_system(raw)
    assert isinstance(ds, DesignSystem)
    assert ds.variables_css == ":root{--brand:#8a5a44;}"
    # Multi-line CSS survives intact, with no escaping artifacts.
    assert ds.components_css == ".hero{padding:16px;}\n.card{border-radius:8px;}"
    # The header partial owns the nav (no separate nav artifact).
    assert ds.header_html == (
        '<header class="site-header">X'
        '<nav class="site-nav"><a href="index.html">Home</a></nav></header>'
    )
    assert "<nav" in ds.header_html
    assert ds.footer_html == '<footer class="site-footer">Y</footer>'


def test_parse_tolerates_surrounding_prose_and_fences():
    raw = (
        "Here is the design system:\n```\n"
        + _delimited(":root{}", ".hero{}",
                     "<header>h<nav>n</nav></header>", "<footer>f</footer>")
        + "```\nThat is all.\n"
    )
    ds = parse_design_system(raw)
    assert ds.variables_css == ":root{}"
    assert ds.footer_html == "<footer>f</footer>"


def test_missing_block_raises_a_clear_error_naming_the_file():
    # A response truncated before the footer block: detectable as a missing
    # marker, not a cryptic JSON crash.
    raw = (
        "===FILE variables.css===\n:root{}\n"
        "===FILE components.css===\n.hero{}\n"
        "===FILE header.html===\n<header>h<nav>n</nav></header>\n"
    )
    with pytest.raises(ValueError) as exc:
        parse_design_system(raw)
    assert "footer.html" in str(exc.value)


def test_stage2_prompt_carries_the_sitemap_slugs_and_titles():
    spec = _spec()
    prompt = build_stage2_prompt(spec)
    # Every page appears as its exact relative filename + title, so stage 2 can
    # link nav/header/footer only to pages that exist.
    for page in spec.pages:
        assert f"{page['slug']}.html" in prompt
        assert page["title"] in prompt
    assert "index.html" in prompt
    # And it is instructed not to invent pages / use web-style routes.
    assert "invent" in prompt.lower() or "do NOT invent" in prompt


def test_stage2_prompt_requests_four_blocks_with_nav_inside_header():
    prompt = build_stage2_prompt(_spec())
    # The format is four blocks: no separate nav.html block.
    assert "===FILE header.html===" in prompt
    assert "===FILE footer.html===" in prompt
    assert "===FILE nav.html===" not in prompt
    # The header is told to own the nav.
    assert "nav" in prompt.lower()


def test_stage2_prompt_constrains_fonts_to_the_palette():
    from webdesign_rl.generate import fonts

    prompt = build_stage2_prompt(_spec())
    # Stage 2 is told to pick font-family ONLY from the palette, named explicitly
    # so the model uses the exact bare family names that resolve OS-level.
    for family in fonts.PALETTE_FAMILIES:
        assert family in prompt
    # And that the display faces are headings-only, not body copy.
    for display in fonts.HEADINGS_ONLY:
        assert display in prompt
    assert "heading" in prompt.lower()


def test_stage2_prompt_names_new_components_as_static_placeholders():
    # Issue 23: the widened catalog adds components (map-embed-placeholder,
    # metric-dashboard, code-snippet) that could tempt an iframe / charting lib /
    # JS. A single minimal clause names them as static / CSS-drawable
    # placeholders so a live run keeps them well-posed.
    prompt = build_stage2_prompt(_spec())
    lowered = prompt.lower()
    assert "placeholder" in lowered
    assert "map-embed-placeholder" in prompt
    assert "metric-dashboard" in prompt
    assert "code-snippet" in prompt


def test_run_stage2_parses_delimited_response_into_design_system():
    raw = _delimited(
        ":root{--brand:#111;}",
        ".hero{}\n.feature-grid{}\n.pricing-table{}",
        "<header>h<nav>n</nav></header>", "<footer>f</footer>",
    )
    client = StubGenerationClient(responses=[raw])
    ds = run_stage2(_spec(), client)
    assert ds.components_css == ".hero{}\n.feature-grid{}\n.pricing-table{}"
    # The call went out at the stage-2 temperature.
    assert client.calls[0][1] == stages.STAGE2_TEMPERATURE
