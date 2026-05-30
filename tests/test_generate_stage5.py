"""Behavioral tests for the stage-5 render-validity gate.

Stage 5 asks "does this site render into a *valid, well-posed* picture?" — it
reuses the already-built ``render_site`` module and checks each page renders
clean, **deterministically** (render twice -> identical pixels), is **not blank**
(content fills the viewport, not near-empty whitespace), has **no catastrophic
layout** (no horizontal overflow / zero-height), and clears the deferred
**substance height bound** (full-page height in [600, 12000] px).

To keep the suite fast (real Chromium renders are slow), most tests inject a
fake ``render`` callable that returns canned :class:`PIL.Image` objects — the
gate's *logic* is what we're testing, not Chromium. One integration test renders
a real stubbed site through the actual ``render_site`` to prove the wiring.
"""

from pathlib import Path

from PIL import Image

from webdesign_rl.generate.quality_gate import run_stage5_gate

VIEWPORT = 1280

PAGE_MAP = {
    "index": {"screenshot": "index.png", "expected_file": "index.html"},
    "about": {"screenshot": "about.png", "expected_file": "about.html"},
}


def _solid(width, height, color=(40, 60, 90)):
    """A non-blank image: a white page with a large content block on it.

    The top-left corner is the (white) page background; the colored block is
    "ink" that fills well over the blank threshold.
    """
    img = Image.new("RGB", (width, height), (255, 255, 255))
    block = Image.new("RGB", (width, max(1, height // 2)), color)
    img.paste(block, (0, height // 4))
    return img


def _mostly_white(width, height, ink_rows=2):
    """A near-empty page: white with only a couple rows of content."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    # Place the ink rows in the vertical middle so the top-left corner (the
    # detected background) stays white.
    mid = height // 2
    for y in range(mid, mid + ink_rows):
        for x in range(width):
            img.putpixel((x, y), (10, 10, 10))
    return img


def _render_stub(images_by_page, *, second_pass=None):
    """A fake ``render`` returning canned images.

    If ``second_pass`` is given, the first call returns ``images_by_page`` and
    the second returns ``second_pass`` (to simulate non-determinism).
    """
    calls = {"n": 0}

    def render(site_dir, page_map, viewport=VIEWPORT):
        calls["n"] += 1
        if second_pass is not None and calls["n"] >= 2:
            return dict(second_pass)
        return dict(images_by_page)

    return render


def _messages(result):
    return " | ".join(d["message"] for d in result.diagnostics)


def _checks(result):
    return {d["check"] for d in result.diagnostics}


# --- Tracer bullet: a good render passes ------------------------------------

def test_good_render_passes(tmp_path):
    images = {
        "index": _solid(VIEWPORT, 900),
        "about": _solid(VIEWPORT, 1500),
    }
    render = _render_stub(images)
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=render)
    assert result.passed is True, _messages(result)
    assert result.diagnostics == []


# --- Not blank --------------------------------------------------------------

def test_near_empty_page_fails_not_blank(tmp_path):
    images = {
        "index": _mostly_white(VIEWPORT, 900),  # near-empty whitespace
        "about": _solid(VIEWPORT, 900),
    }
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=_render_stub(images))
    assert result.passed is False
    assert "not_blank" in _checks(result)
    # Diagnostic names the offending page so repair can target it.
    assert any(d["page"] == "index.html" and d["check"] == "not_blank"
               for d in result.diagnostics)


# --- Determinism ------------------------------------------------------------

def test_non_deterministic_render_fails(tmp_path):
    first = {"index": _solid(VIEWPORT, 900), "about": _solid(VIEWPORT, 900)}
    # Second pass differs for one page.
    second = {"index": _solid(VIEWPORT, 900, color=(200, 10, 10)),
              "about": _solid(VIEWPORT, 900)}
    render = _render_stub(first, second_pass=second)
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=render)
    assert result.passed is False
    assert "deterministic" in _checks(result)
    assert any(d["page"] == "index.html" and d["check"] == "deterministic"
               for d in result.diagnostics)


# --- Catastrophic layout ----------------------------------------------------

def test_horizontal_overflow_fails(tmp_path):
    images = {
        "index": _solid(VIEWPORT + 200, 900),  # wider than the viewport
        "about": _solid(VIEWPORT, 900),
    }
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=_render_stub(images))
    assert result.passed is False
    assert "catastrophic_layout" in _checks(result)
    assert any("overflow" in d["message"] for d in result.diagnostics)


# --- Substance height bound -------------------------------------------------

def test_too_short_page_fails_height_bound(tmp_path):
    images = {
        "index": _solid(VIEWPORT, 400),  # below the 600px floor
        "about": _solid(VIEWPORT, 900),
    }
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=_render_stub(images))
    assert result.passed is False
    assert "substance_height" in _checks(result)
    assert any("600" in d["message"] for d in result.diagnostics)


def test_too_tall_page_fails_height_bound(tmp_path):
    images = {
        "index": _solid(VIEWPORT, 13000),  # above the 12000px ceiling
        "about": _solid(VIEWPORT, 900),
    }
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=_render_stub(images))
    assert result.passed is False
    assert "substance_height" in _checks(result)
    assert any("12000" in d["message"] for d in result.diagnostics)


def test_unrendered_page_fails_render_clean(tmp_path):
    images = {"about": _solid(VIEWPORT, 900)}  # index never rendered
    result = run_stage5_gate(tmp_path, PAGE_MAP, render=_render_stub(images))
    assert result.passed is False
    assert "render_clean" in _checks(result)
    assert any(d["page"] == "index.html" for d in result.diagnostics)


# --- Integration: a real render through the actual render_site --------------

def test_real_render_of_substantial_site_passes(tmp_path):
    """One real-Chromium render (slow) proving the gate wires to render_site.

    A small, hermetic, substantial single page that renders well above the
    600px floor and is clearly not blank.
    """
    (tmp_path / "variables.css").write_text(":root{--ink:#101010;--bg:#f2efe8;}")
    body = "".join(
        f'<section style="height:160px;background:#205080;color:#fff;'
        f'padding:24px"><h2>Section {i}</h2>'
        "<p>Plenty of real descriptive copy that fills the section with "
        "legible content for the agent to study and replicate faithfully.</p>"
        "</section>"
        for i in range(5)
    )
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        '<link rel="stylesheet" href="variables.css">'
        "<style>body{margin:0;background:var(--bg);color:var(--ink);}</style>"
        f"</head><body><main>{body}</main></body></html>"
    )
    page_map = {"index": {"screenshot": "index.png",
                          "expected_file": "index.html"}}
    result = run_stage5_gate(tmp_path, page_map)  # real render_site
    assert result.passed is True, _messages(result)
