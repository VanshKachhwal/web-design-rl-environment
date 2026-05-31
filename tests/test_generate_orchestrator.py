"""Behavioral tests for the bounded-repair orchestrator (``generate_site``).

These drive the whole per-site state machine through the stub client and a
**fake render** (so no real Chromium): stage 1 -> inline gate (<=2 re-rolls) ->
stage 2 -> inline manifest gate (<=2 re-rolls) -> stage 3 fan-out -> full gate
(stage 4 + 5) -> stage-3 nudge loop (<=2/page, composition-only) -> emit/keep,
else drop with a logged reason.

The contract we assert is observable: a fixable page is repaired and the site is
returned; an unfixable page exhausts the budget and the site is dropped with a
logged reason; repair never rewrites the frozen stylesheets; inline-gate failures
re-roll the owning stage <=2x then skip the seed.
"""

import json
from pathlib import Path

from PIL import Image

from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.llm_site_generator import generate_gated_site, Dropped

VIEWPORT = 1280

# --- A good 5-page spec/design the stub feeds ------------------------------

_GOOD_STAGE1 = {
    "brief": "A boutique tea shop, warm minimalist aesthetic.",
    "pages": [
        {"title": "Home", "sections": ["hero", "feature-grid", "card"]},
        {"title": "About", "sections": ["hero", "content-section", "card"]},
        {"title": "Teas", "sections": ["hero", "feature-grid", "card"]},
        {"title": "Pricing", "sections": ["hero", "content-section", "card"]},
        {"title": "Contact", "sections": ["hero", "contact-block", "card"]},
    ],
    "component_manifest": [
        "hero", "feature-grid", "content-section", "card", "contact-block",
    ],
}

_GOOD_STAGE2 = {
    "variables_css": ":root{--brand:#8a5a44;--bg:#faf6f1;--ink:#2b2b2b;"
    "--space:16px;--radius:8px;}",
    "components_css": (
        ".hero{background:var(--bg);padding:var(--space);color:var(--ink);}"
        ".feature-grid{display:grid;gap:var(--space);}"
        ".content-section{padding:var(--space);}"
        ".card{border-radius:var(--radius);background:var(--bg);}"
        ".contact-block{padding:var(--space);}"
    ),
    "header_html": '<header class="site-header"><span>Cha Tea</span>'
    '<nav class="site-nav"><a href="index.html">Home</a></nav></header>',
    "footer_html": '<footer class="site-footer"><p>(c) Cha Tea</p></footer>',
}


def _stage2(fields):
    """Render a stage-2 fields dict as the ===FILE <name>=== delimited format."""
    return (
        "===FILE variables.css===\n" + fields["variables_css"] + "\n"
        "===FILE components.css===\n" + fields["components_css"] + "\n"
        "===FILE header.html===\n" + fields["header_html"] + "\n"
        "===FILE footer.html===\n" + fields["footer_html"] + "\n"
    )

# A rich body using >=3 distinct catalog components and >=50 words.
_GOOD_BODY = (
    '<main class="page">'
    '<section class="hero"><h1>Welcome</h1>'
    "<p>We are a boutique tea shop sourcing single-origin leaves from small "
    "family farms across the world. Every batch is roasted in small lots and "
    "tasted before it ever reaches your cup, so you always get something "
    "genuinely remarkable and fresh every single season.</p></section>"
    '<section class="feature-grid"><div class="card"><h2>Loose Leaf</h2>'
    "<p>Hand-blended seasonal selections delivered to your door each month.</p>"
    "</div></section>"
    '<section class="content-section"><h2>Our Story</h2>'
    "<p>Open daily from morning until evening in the heart of the old town.</p>"
    "</section></main>"
)

# A body that fails stage-4 substance (only 1 distinct component, few words).
_BAD_BODY = (
    '<main class="page"><section class="hero"><h1>Hi</h1>'
    "<p>Too short.</p></section></main>"
)

_SEED = {
    "archetype": "tea-shop",
    "aesthetic": "warm-minimal",
    "complexity": "low",
    "audience": "local-community",
    "brand_mood": "warm",
    "seed_tuple": ["tea-shop", "warm-minimal", "low", "local-community", "warm"],
}


def _solid(width=VIEWPORT, height=900, color=(40, 60, 90)):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    block = Image.new("RGB", (width, max(1, height // 2)), color)
    img.paste(block, (0, height // 4))
    return img


def _fake_render(site_dir, page_map, viewport=VIEWPORT):
    """A deterministic fake render: every page is a good, non-blank image."""
    return {name: _solid() for name in page_map}


def _all_good_responses():
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"]]
    return responses


# --- Tracer bullet: a clean site passes the whole machine and is returned ---

def test_clean_site_passes_and_is_returned(tmp_path):
    client = StubGenerationClient(responses=_all_good_responses())
    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Path)
    assert (result / "index.html").exists()
    assert (result / "variables.css").exists()


# --- Stage-3 nudge loop: a fixable page is repaired within <=2 nudges -------

def test_fixable_page_is_repaired_within_budget(tmp_path):
    # index starts with a bad (thin) body; the first nudge returns a good body.
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)                       # index: stage-3, fails
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]  # rest good
    responses.append(_GOOD_BODY)                      # index: nudge #1, fixed
    client = StubGenerationClient(responses=responses)

    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Path), getattr(result, "reason", result)
    # The repaired page now has the rich body.
    assert "Our Story" in (result / "index.html").read_text()


def test_nudged_body_with_in_body_chrome_is_normalized(tmp_path):
    # The nudge loop must normalize stage-3 output too: a repair that re-adds
    # in-body chrome (the unrepairable live failure) is stripped, so the page
    # keeps exactly the injected chrome and passes the chrome-identity gate.
    import re

    dirty_good = (
        '<main class="page">'
        '<header class="bogus"><nav><a href="#">X</a></nav></header>'
        + _GOOD_BODY[len('<main class="page">'):]
    )
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)                       # index: stage-3, fails
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]  # rest good
    responses.append(dirty_good)                      # index: nudge #1, dirty
    client = StubGenerationClient(responses=responses)

    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Path), getattr(result, "reason", result)
    text = (result / "index.html").read_text()
    assert len(re.findall(r"<header\b", text)) == 1
    assert len(re.findall(r"<nav\b", text)) == 1
    main = re.search(r"<main.*?</main>", text, re.DOTALL).group(0)
    assert "<header" not in main and "<nav" not in main


def test_default_nudge_budget_is_five(tmp_path):
    # A page that only comes good on the 4th nudge is still repaired under the
    # default budget (5), proving the default rose from 2 to 5.
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)                       # index: initial, fails
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]
    responses += [_BAD_BODY, _BAD_BODY, _BAD_BODY]    # nudges 1-3: still bad
    responses.append(_GOOD_BODY)                      # nudge 4: fixed
    client = StubGenerationClient(responses=responses)

    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Path), getattr(result, "reason", result)
    assert "Our Story" in (result / "index.html").read_text()


def test_unfixable_page_exhausts_budget_and_drops_with_reason(tmp_path, caplog):
    # With an explicit budget of 2, index stays thin through the initial attempt
    # + both nudges -> dropped (the exhaustion path is unchanged at the limit).
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)                       # index: initial, fails
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]
    responses.append(_BAD_BODY)                       # nudge #1: still bad
    responses.append(_BAD_BODY)                       # nudge #2: still bad
    client = StubGenerationClient(responses=responses)

    import logging
    with caplog.at_level(logging.WARNING):
        result = generate_gated_site(
            _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render,
            max_nudges=2,
        )
    assert isinstance(result, Dropped)
    assert "index.html" in result.reason
    # The drop is logged with its reason (no silent attrition).
    assert any("dropping site" in rec.message for rec in caplog.records)


def test_repair_never_rewrites_frozen_stylesheets(tmp_path):
    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]
    responses.append(_GOOD_BODY)                      # nudge fixes index
    client = StubGenerationClient(responses=responses)

    out = tmp_path / "site"
    # Capture the stylesheets right after they are first frozen by hooking the
    # render to snapshot on its first call.
    snapshots = {}

    def render(site_dir, page_map, viewport=VIEWPORT):
        if "vars" not in snapshots:
            snapshots["vars"] = (Path(site_dir) / "variables.css").read_text()
            snapshots["comp"] = (Path(site_dir) / "components.css").read_text()
        return _fake_render(site_dir, page_map, viewport)

    result = generate_gated_site(_SEED, client=client, out_dir=out, render=render)
    assert isinstance(result, Path)
    # The frozen stylesheets are byte-identical before and after repair.
    assert (out / "variables.css").read_text() == snapshots["vars"]
    assert (out / "components.css").read_text() == snapshots["comp"]
    assert snapshots["vars"] == _GOOD_STAGE2["variables_css"]


# --- Progress logging (issue 11) -------------------------------------------

def test_pipeline_emits_ordered_progress_logging(tmp_path, caplog):
    import logging

    client = StubGenerationClient(responses=_all_good_responses())
    with caplog.at_level(logging.INFO,
                         logger="webdesign_rl.generate.llm_site_generator"):
        result = generate_gated_site(
            _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
        )
    assert isinstance(result, Path), getattr(result, "reason", result)
    text = "\n".join(rec.message for rec in caplog.records)
    # Each stage announces itself, with per-page progress and the gate.
    assert "stage 1" in text.lower()
    assert "stage 2" in text.lower()
    assert "page 1/5" in text          # stage-3 per-page i/N: <title>
    assert "Home" in text              # the page title is logged
    assert "gate" in text.lower()
    # No secret/API key material is ever logged.
    assert "ANTHROPIC_API_KEY" not in text and "sk-" not in text


def test_repair_nudges_are_logged_with_attempt_and_slug(tmp_path, caplog):
    import logging

    responses = [json.dumps(_GOOD_STAGE1), _stage2(_GOOD_STAGE2)]
    responses.append(_BAD_BODY)
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"][1:]]
    responses.append(_GOOD_BODY)                      # nudge #1 fixes index
    client = StubGenerationClient(responses=responses)

    with caplog.at_level(logging.INFO,
                         logger="webdesign_rl.generate.llm_site_generator"):
        result = generate_gated_site(
            _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
        )
    assert isinstance(result, Path), getattr(result, "reason", result)
    text = "\n".join(rec.message for rec in caplog.records)
    assert "nudging index" in text
    assert "1/5" in text  # attempt k/budget


# --- Inline gates -----------------------------------------------------------

def test_stage1_short_sitemap_rerolls_then_skips_seed(tmp_path, caplog):
    short = {
        "brief": "Too small.",
        "pages": [{"title": "Home", "sections": ["hero"]},
                  {"title": "About", "sections": ["hero"]}],
        "component_manifest": ["hero"],
    }
    # 3 stage-1 attempts (initial + 2 re-rolls), all short -> skip the seed.
    responses = [json.dumps(short), json.dumps(short), json.dumps(short)]
    client = StubGenerationClient(responses=responses)

    import logging
    with caplog.at_level(logging.WARNING):
        result = generate_gated_site(
            _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
        )
    assert isinstance(result, Dropped)
    assert "stage-1" in result.reason and "5" in result.reason
    # Exactly 3 stage-1 calls were made (initial + MAX_REROLLS), then it gave up.
    assert len(client.calls) == 3


def test_stage1_reroll_recovers_when_a_later_attempt_is_good(tmp_path):
    short = {
        "brief": "Too small.",
        "pages": [{"title": "Home", "sections": ["hero"]}],
        "component_manifest": ["hero"],
    }
    responses = [json.dumps(short), json.dumps(_GOOD_STAGE1),
                 _stage2(_GOOD_STAGE2)]
    responses += [_GOOD_BODY for _ in _GOOD_STAGE1["pages"]]
    client = StubGenerationClient(responses=responses)

    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Path), getattr(result, "reason", result)


def test_stage2_missing_component_rerolls_then_skips_seed(tmp_path):
    bad_stage2 = dict(_GOOD_STAGE2)
    # components.css styles nothing for the manifest -> manifest gate fails.
    bad_stage2["components_css"] = ".unrelated{color:var(--ink);}"
    responses = [json.dumps(_GOOD_STAGE1),
                 _stage2(bad_stage2), _stage2(bad_stage2),
                 _stage2(bad_stage2)]
    client = StubGenerationClient(responses=responses)

    result = generate_gated_site(
        _SEED, client=client, out_dir=tmp_path / "site", render=_fake_render
    )
    assert isinstance(result, Dropped)
    assert "stage-2" in result.reason
    # 1 stage-1 + 3 stage-2 attempts = 4 calls, then it gave up.
    assert len(client.calls) == 4
