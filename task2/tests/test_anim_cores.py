"""Fast, deterministic unit tests for Task 2's pure cores — no API, no browser.

Mirrors Task 1's split: the stochastic/IO bits (Playwright render, VLM judges,
Harbor) are untested shell; the deterministic logic is unit-tested here.

Run: ``PYTHONPATH=task2 .venv/bin/python -m pytest task2/tests -q``
"""

import pytest
from PIL import Image

from webdesign_rl_anim.anim_judge import (
    RUBRIC_FIELDS,
    StubAnimationJudgeClient,
    judge_rubric,
)
from webdesign_rl_anim.filmstrip import contact_sheet
from webdesign_rl_anim.generate_anim import _extract_html
from webdesign_rl_anim.motion import motion_score
from webdesign_rl_anim.perturb_anim import _OVERRIDES, make_variant


def _frame(color, size=(120, 200)):
    return Image.new("RGB", size, color)


# ---- motion term -----------------------------------------------------------

def test_motion_identical_filmstrips_score_one():
    frames = [_frame((0, 0, 0)), _frame((255, 255, 255)), _frame((0, 0, 0))]
    assert motion_score(frames, frames) == pytest.approx(1.0, abs=1e-5)


def test_motion_static_candidate_scores_near_zero():
    moving = [_frame((0, 0, 0)), _frame((255, 255, 255)), _frame((0, 0, 0))]
    still = [_frame((128, 128, 128))] * 3  # no change between frames -> no motion
    assert motion_score(moving, still) < 0.05


def test_motion_partial_beats_none():
    ref = [_frame((0, 0, 0)), _frame((255, 255, 255)), _frame((0, 0, 0))]
    # candidate moves, but less far (grey instead of white) — partial motion
    partial = [_frame((0, 0, 0)), _frame((130, 130, 130)), _frame((0, 0, 0))]
    still = [_frame((128, 128, 128))] * 3
    assert motion_score(ref, partial) > motion_score(ref, still)


def test_motion_length_mismatch_is_zero():
    a = [_frame((0, 0, 0)), _frame((255, 255, 255))]
    b = [_frame((0, 0, 0))]
    assert motion_score(a, b) == 0.0


# ---- contact sheet ---------------------------------------------------------

def test_contact_sheet_stacks_uniform_width():
    frames = [_frame((10, 10, 10), (200, 100)), _frame((20, 20, 20), (200, 300))]
    sheet = contact_sheet(frames, [0, 500], thumb_w=160)
    # uniform width + padding; height grows with the (scaled) stacked frames.
    assert sheet.width == 160 + 2 * 8
    assert sheet.height > 160  # at least the taller scaled frame + labels


# ---- animation judge plumbing (stub: no API) -------------------------------

def test_judge_rubric_normalizes_and_averages():
    stub = StubAnimationJudgeClient(
        {"motion_presence": 10, "timing": 5, "easing_feel": 0, "motion_type": 5}
    )
    out = judge_rubric(_frame((0, 0, 0)), _frame((1, 1, 1)), stub)
    assert set(out["sub_scores"]) == set(RUBRIC_FIELDS)
    assert out["animation_judge"] == (1.0 + 0.5 + 0.0 + 0.5) / 4


def test_judge_malformed_rubric_floors_to_zero():
    out = judge_rubric(_frame((0, 0, 0)), _frame((1, 1, 1)),
                       StubAnimationJudgeClient("not a dict"))
    assert out["animation_judge"] == 0.0


# ---- perturbation injection ------------------------------------------------

def test_make_variant_injects_override_before_body_close():
    html = "<html><head></head><body><h1>hi</h1></body></html>"
    out = make_variant(html, "static")
    assert _OVERRIDES["static"] in out
    assert out.index("perturb-static") < out.index("</body>")


def test_make_variant_oracle_is_identity():
    html = "<html><body>x</body></html>"
    assert make_variant(html, "oracle") == html


# ---- generation HTML extraction --------------------------------------------

def test_extract_html_strips_surrounding_prose_and_fences():
    reply = "Sure!\n```html\n<!doctype html><html><body>ok</body></html>\n```\nDone."
    assert _extract_html(reply) == "<!doctype html><html><body>ok</body></html>"
