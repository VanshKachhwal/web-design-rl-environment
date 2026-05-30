"""End-to-end behavioral tests for the grade() orchestrator (live-render path).

Since issue 05 the grader takes a candidate *directory of HTML/CSS*: it renders
the candidate itself (headless Chromium over a local HTTP server) and compares
the rendered screenshot to a committed reference PNG. These tests drive the full
spine (render -> metric -> aggregate -> write) and assert only the written reward
outputs. The judge term is pinned with a ``StubJudgeClient`` so there are no live
API calls.
"""

import json

from webdesign_rl.grade.grader import grade
from webdesign_rl.grade.judge import StubJudgeClient

# page_map now maps a page to its reference screenshot PNG (in reference_dir) and
# the required candidate HTML file (in candidate_dir) the grader will render.
HOME_ONLY = {"home": {"screenshot": "home.png", "expected_file": "index.html"}}
HOME_AND_ABOUT = {
    "home": {"screenshot": "home.png", "expected_file": "index.html"},
    "about": {"screenshot": "home.png", "expected_file": "about.html"},
}

# A perfect-rubric stub so the (non-deterministic) judge term is pinned to 1.0 in
# the deterministic grader tests — no live API calls.
PERFECT_RUBRIC = {
    "layout_alignment": 10,
    "color_palette": 10,
    "typography": 10,
    "content_completeness": 10,
}


def _perfect_judge():
    return StubJudgeClient(PERFECT_RUBRIC)


def _load_reward(out_dir):
    return json.loads((out_dir / "reward.json").read_text())


def test_perfect_candidate_scores_all_dimensions_near_one(site_dirs, tmp_path):
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    # The perfect candidate is the same HTML the reference PNG was rendered from,
    # so the deterministic dims land at ~1.0.
    assert reward["structure"] > 0.99
    assert reward["color"] > 0.99
    assert reward["content"] > 0.99
    assert reward["design_judge"] == 1.0
    assert reward["reward"] > 0.99


def test_reward_json_has_expected_keys_and_ranges(site_dirs, tmp_path):
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    assert set(reward.keys()) == {
        "reward",
        "structure",
        "color",
        "content",
        "design_judge",
    }
    for value in reward.values():
        assert isinstance(value, float)
        assert 0.0 <= value <= 1.0


def test_wrong_color_candidate_scores_lower(site_dirs, tmp_path):
    # Same layout and text as the reference, wrong palette: the color term (and
    # so the overall reward) must drop below the perfect candidate's.
    def reward_for(name):
        out = tmp_path / name
        grade(site_dirs[name], site_dirs["reference"], HOME_ONLY, out, _perfect_judge())
        return _load_reward(out)

    perfect = reward_for("perfect")
    wrongcolor = reward_for("wrongcolor")
    assert wrongcolor["color"] < perfect["color"]
    assert wrongcolor["reward"] < perfect["reward"]


def test_design_judge_term_flows_into_reward(site_dirs, tmp_path):
    judge = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    grade(site_dirs["perfect"], site_dirs["reference"], HOME_ONLY, tmp_path, judge)
    reward = _load_reward(tmp_path)
    assert reward["design_judge"] == 0.7


def test_missing_required_page_drags_reward_to_half(site_dirs, tmp_path):
    # home is perfect (~1.0 across all four dims); about.html is absent from the
    # candidate directory, so it renders to nothing and scores 0.
    grade(
        site_dirs["missing"],
        site_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    assert 0.45 < reward["reward"] <= 0.5


def test_reward_details_reports_per_page_and_missing(site_dirs, tmp_path):
    grade(
        site_dirs["missing"],
        site_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    pages = details["pages"]
    assert pages["home"]["present"] is True
    assert pages["home"]["structure"] > 0.99
    assert pages["home"]["color"] > 0.99
    assert pages["home"]["content"] > 0.99
    assert pages["home"]["design_judge"] == 1.0
    assert pages["about"]["present"] is False
    assert pages["about"]["structure"] == 0.0
    assert pages["about"]["color"] == 0.0
    assert pages["about"]["content"] == 0.0
    assert pages["about"]["design_judge"] == 0.0


def test_reward_details_records_judge_sub_scores(site_dirs, tmp_path):
    judge = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    grade(site_dirs["perfect"], site_dirs["reference"], HOME_ONLY, tmp_path, judge)
    details = json.loads((tmp_path / "reward-details.json").read_text())
    sub = details["pages"]["home"]["design_judge_sub_scores"]
    assert sub == {
        "layout_alignment": 0.8,
        "color_palette": 0.6,
        "typography": 1.0,
        "content_completeness": 0.4,
    }
