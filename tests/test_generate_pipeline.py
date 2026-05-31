"""Behavioral tests for the 3-stage ``generate_site`` pipeline (stubbed LLM).

These exercise the whole pipeline end-to-end through the stubbable client, with
canned stage outputs and **no live API call**. They assert the externally
observable contract of a generated site directory:

- a multi-page (>=5) static HTML/CSS site,
- the frozen design-system artifacts (``variables.css``, ``components.css``,
  the header — which contains the site nav — and footer partials),
- one HTML file per sitemap page, named by its slug,
- a ``page_map`` in the emit/grader shape,
- chrome (header + footer) injected byte-identically across pages,
- pages referencing only the frozen stylesheets (no other linked stylesheet).
"""

import json
import re
from pathlib import Path

from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.llm_site_generator import generate_site

# A six-page canned sitemap (>=5) so the produced site clears the page floor.
_STAGE1 = {
    "brief": "A boutique tea shop, warm minimalist aesthetic.",
    "pages": [
        {"title": "Home", "sections": ["hero", "feature-grid"]},
        {"title": "About Us", "sections": ["content-section"]},
        {"title": "Our Teas", "sections": ["card", "feature-grid"]},
        {"title": "Pricing", "sections": ["pricing-table"]},
        {"title": "Blog", "sections": ["blog-post-card"]},
        {"title": "Contact", "sections": ["contact-block"]},
    ],
    "component_manifest": [
        "hero",
        "feature-grid",
        "content-section",
        "card",
        "pricing-table",
        "blog-post-card",
        "contact-block",
    ],
}

# Stage 2 returns the escape-free ===FILE <name>=== delimited format, four
# blocks — the header owns the site nav (no separate nav block).
_STAGE2 = (
    "===FILE variables.css===\n"
    ":root{--brand:#8a5a44;--bg:#faf6f1;--space:16px;}\n"
    "===FILE components.css===\n"
    ".hero{background:var(--bg);padding:var(--space);}.card{border-radius:8px;}\n"
    "===FILE header.html===\n"
    '<header class="site-header"><span>Cha Tea</span>'
    '<nav class="site-nav"><a href="index.html">Home</a>'
    '<a href="about-us.html">About</a></nav></header>\n'
    "===FILE footer.html===\n"
    '<footer class="site-footer"><p>(c) Cha Tea</p></footer>\n'
)


def _stage3_body(title):
    # Stage 3 returns just the page's <main> body markup (composition only).
    return (
        f'<main class="page"><section class="hero"><h1>{title}</h1>'
        f"<p>Welcome to our {title} page with plenty of real words here.</p>"
        "</section></main>"
    )


_SEED = {
    "archetype": "tea-shop",
    "aesthetic": "warm-minimal",
    "complexity": "low",
    "audience": "local-community",
    "brand_mood": "warm-and-welcoming",
    "seed_tuple": [
        "tea-shop",
        "warm-minimal",
        "low",
        "local-community",
        "warm-and-welcoming",
    ],
}


def _stubbed_run(tmp_path) -> Path:
    # 1 stage-1 call + 1 stage-2 call + one stage-3 call per page (6) = 8 calls.
    responses = [json.dumps(_STAGE1), _STAGE2]
    responses += [_stage3_body(p["title"]) for p in _STAGE1["pages"]]
    client = StubGenerationClient(responses=responses)
    return generate_site(_SEED, client=client, out_dir=tmp_path / "site")


def test_generate_site_makes_no_live_api_call(tmp_path):
    # The stub raises if asked for more responses than canned; a clean run with
    # exactly the canned set proves the pipeline never reached past the stub.
    site_dir = _stubbed_run(tmp_path)
    assert site_dir.is_dir()


def test_generated_site_has_at_least_five_pages(tmp_path):
    site_dir = _stubbed_run(tmp_path)
    html_pages = sorted(
        p.name
        for p in site_dir.glob("*.html")
    )
    assert len(html_pages) >= 5
    assert "index.html" in html_pages


def test_generated_site_has_frozen_design_system_artifacts(tmp_path):
    site_dir = _stubbed_run(tmp_path)
    assert (site_dir / "variables.css").exists()
    assert (site_dir / "components.css").exists()


def test_page_map_is_in_emit_grader_shape(tmp_path):
    site_dir = _stubbed_run(tmp_path)
    page_map = json.loads((site_dir / "page_map.json").read_text())
    assert "index" in page_map
    for slug, spec in page_map.items():
        assert spec == {
            "screenshot": f"{slug}.png",
            "expected_file": f"{slug}.html",
        }
        assert (site_dir / spec["expected_file"]).exists()


def test_chrome_is_byte_identical_across_pages(tmp_path):
    site_dir = _stubbed_run(tmp_path)
    chrome_blocks = []
    for html_file in site_dir.glob("*.html"):
        text = html_file.read_text()
        # Exactly one header (containing exactly one nav) and one footer.
        assert len(re.findall(r"<header\b", text)) == 1
        assert len(re.findall(r"<nav\b", text)) == 1
        assert len(re.findall(r"<footer\b", text)) == 1
        header = re.search(r"<header.*?</header>", text, re.DOTALL).group(0)
        footer = re.search(r"<footer.*?</footer>", text, re.DOTALL).group(0)
        # The nav lives inside the header.
        assert "<nav" in header
        chrome_blocks.append((header, footer))
    # Every page's chrome pair is identical to the first page's.
    assert all(block == chrome_blocks[0] for block in chrome_blocks)


def test_in_body_chrome_is_stripped_before_assembly(tmp_path):
    # Regression for the live failure (Bug A): stage 3 wrongly returns a full
    # header/nav/footer *inside* <main>, with placeholder # links. The pipeline
    # must strip it so the assembled page has exactly one header (one nav, the
    # stage-2 one) and one footer, and zero chrome inside <main>.
    dirty_body = (
        '<main class="page">'
        '<header class="bogus"><nav><a href="#">Home</a></nav></header>'
        '<section class="hero"><h1>Home</h1>'
        "<p>Plenty of real words on this page for substance and content.</p>"
        "</section>"
        '<footer class="bogus"><p>bogus</p></footer>'
        "</main>"
    )
    responses = [json.dumps(_STAGE1), _STAGE2]
    responses += [dirty_body for _ in _STAGE1["pages"]]
    client = StubGenerationClient(responses=responses)
    site_dir = generate_site(_SEED, client=client, out_dir=tmp_path / "site")

    for html_file in site_dir.glob("*.html"):
        text = html_file.read_text()
        assert len(re.findall(r"<header\b", text)) == 1
        assert len(re.findall(r"<nav\b", text)) == 1
        assert len(re.findall(r"<footer\b", text)) == 1
        # The surviving nav is the stage-2 one (index.html link), not the
        # placeholder "#" stage-3 one.
        nav = re.search(r"<nav.*?</nav>", text, re.DOTALL).group(0)
        assert 'href="index.html"' in nav
        assert 'href="#"' not in nav
        # No chrome inside <main>.
        main = re.search(r"<main.*?</main>", text, re.DOTALL).group(0)
        assert "<header" not in main
        assert "<nav" not in main
        assert "<footer" not in main


def test_generated_site_records_its_seed_tuple(tmp_path):
    # Each site persists its seed tuple for auditability and curation.
    site_dir = _stubbed_run(tmp_path)
    seed_record = json.loads((site_dir / "seed.json").read_text())
    assert seed_record["seed_tuple"] == _SEED["seed_tuple"]


def test_pages_reference_only_the_frozen_stylesheets(tmp_path):
    site_dir = _stubbed_run(tmp_path)
    for html_file in site_dir.glob("*.html"):
        text = html_file.read_text()
        stylesheets = set(re.findall(r'<link[^>]+href="([^"]+)"', text))
        assert stylesheets <= {"variables.css", "components.css"}
        # No external resource of any kind.
        assert "http://" not in text and "https://" not in text
        # Static-only: no script tags.
        assert "<script" not in text.lower()
