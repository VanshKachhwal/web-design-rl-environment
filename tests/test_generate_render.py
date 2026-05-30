"""Integration check: a stubbed generated site renders via the existing module.

This is the issue-01 "generate one site, render it locally" path, end to end and
deterministic: a stubbed pipeline produces a site dir, which the *already built*
``render_site`` turns into one full-page 1280px screenshot per page. It is the
lightweight proof that generation output is renderable by the same module the
grader uses — no new rendering code.
"""

import json
from pathlib import Path

from PIL import Image

from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.llm_site_generator import generate_site
from webdesign_rl.render.browser import render_site

_STAGE1 = {
    "brief": "A small architecture studio, bold editorial aesthetic.",
    "pages": [
        {"title": "Home", "sections": ["hero"]},
        {"title": "Studio", "sections": ["content-section"]},
        {"title": "Projects", "sections": ["feature-grid"]},
        {"title": "Process", "sections": ["content-section"]},
        {"title": "Contact", "sections": ["contact-block"]},
    ],
    "component_manifest": ["hero", "content-section", "feature-grid", "contact-block"],
}

_STAGE2 = {
    "variables_css": ":root{--ink:#101010;--paper:#f4f1ea;--accent:#d6452b;}",
    "components_css": (
        "body{margin:0;font-family:Inter;color:var(--ink);background:var(--paper);}"
        ".site-header{background:var(--ink);color:var(--paper);padding:24px;}"
        ".hero{padding:80px 24px;background:var(--accent);color:var(--paper);}"
        "main{padding:40px 24px;min-height:600px;}"
    ),
    "header_html": '<header class="site-header"><strong>FORM STUDIO</strong></header>',
    "nav_html": '<nav class="site-nav"><a href="index.html">Home</a></nav>',
    "footer_html": '<footer class="site-footer">FORM STUDIO 2026</footer>',
}


def _stage3_body(title):
    return (
        f'<main><section class="hero"><h1>{title}</h1>'
        f"<p>This is the {title} page of a bold editorial architecture studio "
        "with real descriptive copy to fill the layout meaningfully.</p>"
        "</section></main>"
    )


def test_generated_site_renders_one_screenshot_per_page_at_1280(tmp_path):
    responses = [json.dumps(_STAGE1), json.dumps(_STAGE2)]
    responses += [_stage3_body(p["title"]) for p in _STAGE1["pages"]]
    client = StubGenerationClient(responses=responses)

    site_dir = generate_site(
        {"archetype": "architecture", "aesthetic": "editorial", "complexity": "med"},
        client=client,
        out_dir=tmp_path / "site",
    )
    page_map = json.loads((site_dir / "page_map.json").read_text())

    images = render_site(site_dir, page_map, viewport=1280)

    # One full-page screenshot per sitemap page, all at the fixed 1280px width.
    assert set(images) == set(page_map)
    for image in images.values():
        assert isinstance(image, Image.Image)
        assert image.width == 1280
        assert image.height > 0
