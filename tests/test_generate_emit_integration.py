"""Issue-04 close-the-loop test: a gated site -> a runnable Harbor task.

This is the first full local end-to-end: a stubbed-LLM site is run through the
gated orchestrator (a fast fake render drives stage 5), the survivor is handed to
the *existing* emit packaging, and we assert the emitted task has the expected
Harbor shape and that the oracle's bundled site reproduces the reference exactly
(the basis for ``harbor run oracle`` scoring ~= 1.0).

The live ``harbor run -a oracle`` reward-~=1.0 check is Docker-gated and run as a
manual/CI step (see the issue's acceptance criteria); here we assert the emitted
structure + the oracle's byte-exact reproduction, which is what makes that
ceiling hold deterministically.
"""

import filecmp
import json
import tomllib
from pathlib import Path

from PIL import Image

from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.llm_site_generator import generate_gated_site
from webdesign_rl.emit import build_task

VIEWPORT = 1280

# A small, hermetic, substantial 5-page site whose pages really render above the
# 600px substance floor (stage-5 uses the fake render; build_task's agent
# screenshots use it too here, since the default in-container render needs Docker
# and this test asserts packaging structure, not font fidelity).
_STAGE1 = {
    "brief": "A small architecture studio, bold editorial aesthetic.",
    "pages": [
        {"title": "Home", "sections": ["hero", "feature-grid", "card"]},
        {"title": "Studio", "sections": ["hero", "content-section", "card"]},
        {"title": "Projects", "sections": ["hero", "feature-grid", "card"]},
        {"title": "Process", "sections": ["hero", "content-section", "card"]},
        {"title": "Contact", "sections": ["hero", "contact-block", "card"]},
    ],
    "component_manifest": [
        "hero", "feature-grid", "content-section", "card", "contact-block",
    ],
}

_STAGE2 = (
    "===FILE variables.css===\n"
    ":root{--ink:#101010;--paper:#f4f1ea;--accent:#d6452b;--space:24px;"
    "--radius:6px;}\n"
    "===FILE components.css===\n"
    "body{margin:0;color:var(--ink);background:var(--paper);}"
    ".site-header{background:var(--ink);color:var(--paper);padding:var(--space);}"
    ".hero{padding:var(--space);background:var(--accent);color:var(--paper);}"
    ".feature-grid{display:grid;gap:var(--space);padding:var(--space);}"
    ".content-section{padding:var(--space);}"
    ".card{border-radius:var(--radius);padding:var(--space);"
    "background:var(--paper);}"
    ".contact-block{padding:var(--space);}\n"
    "===FILE header.html===\n"
    '<header class="site-header"><strong>FORM STUDIO</strong>'
    '<nav class="site-nav"><a href="index.html">Home</a></nav></header>\n'
    "===FILE footer.html===\n"
    '<footer class="site-footer">FORM STUDIO 2026</footer>\n'
)


def _body(title):
    return (
        '<main class="page">'
        f'<section class="hero"><h1>{title}</h1>'
        "<p>This is the page of a bold editorial architecture studio with real "
        "descriptive copy filling the layout meaningfully across several lines "
        "so the rendered page clears the substance floor comfortably.</p>"
        "</section>"
        '<section class="feature-grid">'
        '<div class="card"><h2>Selected Work</h2>'
        "<p>A curated set of recent residential and civic projects.</p></div>"
        "</section>"
        '<section class="content-section">'
        "<h2>Our Approach</h2>"
        "<p>We design calm, durable spaces grounded in their context.</p>"
        "</section></main>"
    )


_SEED = {
    "archetype": "architecture",
    "aesthetic": "editorial",
    "complexity": "low",
    "audience": "civic",
    "brand_mood": "bold",
    "seed_tuple": ["architecture", "editorial", "low", "civic", "bold"],
}


def _solid(width=VIEWPORT, height=1400, color=(40, 60, 90)):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    block = Image.new("RGB", (width, max(1, height // 2)), color)
    img.paste(block, (0, height // 4))
    return img


def _fake_render(site_dir, page_map, viewport=VIEWPORT):
    return {name: _solid() for name in page_map}


def _gated_site(out_dir):
    responses = [json.dumps(_STAGE1), _STAGE2]
    responses += [_body(p["title"]) for p in _STAGE1["pages"]]
    client = StubGenerationClient(responses=responses)
    result = generate_gated_site(
        _SEED, client=client, out_dir=out_dir, render=_fake_render
    )
    assert isinstance(result, Path), getattr(result, "reason", result)
    return result


def test_gated_site_emits_a_runnable_harbor_task(tmp_path):
    site = _gated_site(tmp_path / "site")
    page_map = json.loads((site / "page_map.json").read_text())

    task = build_task(site, page_map, tmp_path / "task", render=_fake_render)

    # Canonical Harbor skeleton (mirrors the emit-layer tests).
    assert (task / "instruction.md").is_file()
    assert (task / "task.toml").is_file()
    assert (task / "environment" / "Dockerfile").is_file()
    assert (task / "solution" / "solve.sh").is_file()
    assert (task / "tests" / "Dockerfile").is_file()
    assert (task / "tests" / "test.sh").is_file()

    # The verifier env is separate (grading code hidden from the agent).
    cfg = tomllib.loads((task / "task.toml").read_text())
    assert cfg["verifier"]["environment_mode"] == "separate"

    # The reference site + page_map are baked into the verifier build context.
    baked_map = json.loads((task / "tests" / "page_map.json").read_text())
    assert baked_map == page_map
    for spec in page_map.values():
        assert (task / "tests" / "reference_site" / spec["expected_file"]).is_file()


def test_oracle_reproduces_the_gated_reference_exactly(tmp_path):
    # The oracle bundles the ground-truth HTML and publishes it verbatim, so its
    # output IS the reference site -> the grader's deterministic ceiling (~1.0).
    site = _gated_site(tmp_path / "site")
    page_map = json.loads((site / "page_map.json").read_text())
    task = build_task(site, page_map, tmp_path / "task", render=_fake_render)

    oracle_site = task / "solution" / "site"
    # Every page + the frozen stylesheets are bundled byte-identically.
    for name in ["variables.css", "components.css"] + [
        spec["expected_file"] for spec in page_map.values()
    ]:
        assert (oracle_site / name).is_file()
        assert filecmp.cmp(site / name, oracle_site / name, shallow=False), name
