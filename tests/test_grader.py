"""End-to-end behavioral tests for the grade() orchestrator.

These exercise the full spine (load -> metric -> aggregate -> write) on committed
PNG fixtures and assert only the written reward outputs.
"""

import json

from webdesign_rl.grade.grader import grade
from webdesign_rl.grade.judge import StubJudgeClient

HOME_ONLY = {"home": {"screenshot": "home.png", "expected_file": "home.png"}}
HOME_AND_ABOUT = {
    "home": {"screenshot": "home.png", "expected_file": "home.png"},
    "about": {"screenshot": "about.png", "expected_file": "about.png"},
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


def test_perfect_candidate_scores_all_dimensions_near_one(fixture_dirs, tmp_path):
    grade(
        fixture_dirs["perfect"],
        fixture_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    assert reward["structure"] > 0.99
    assert reward["color"] > 0.99
    assert reward["design_judge"] == 1.0
    assert reward["reward"] > 0.99


def test_reward_json_has_expected_keys_and_ranges(fixture_dirs, tmp_path):
    grade(
        fixture_dirs["perfect"],
        fixture_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    # Flat object: the scalar reward plus the structure, color, and design_judge
    # dimensions.
    assert set(reward.keys()) == {"reward", "structure", "color", "design_judge"}
    for value in reward.values():
        assert isinstance(value, float)
        assert 0.0 <= value <= 1.0


def test_worse_candidates_score_lower(fixture_dirs, tmp_path):
    def reward_for(name):
        out = tmp_path / name
        grade(
            fixture_dirs[name],
            fixture_dirs["reference"],
            HOME_ONLY,
            out,
            _perfect_judge(),
        )
        return _load_reward(out)["reward"]

    perfect = reward_for("perfect")
    blurred = reward_for("blurred")
    different = reward_for("different")
    assert perfect > blurred > different


def test_design_judge_term_flows_into_reward(fixture_dirs, tmp_path):
    # With a stubbed mixed rubric the design_judge dimension lands at its
    # averaged [0, 1] value (no live API call), independent of the pixel terms.
    judge = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    grade(
        fixture_dirs["perfect"], fixture_dirs["reference"], HOME_ONLY, tmp_path, judge
    )
    reward = _load_reward(tmp_path)
    assert reward["design_judge"] == 0.7


def test_missing_required_page_drags_reward_to_half(fixture_dirs, tmp_path):
    # home is perfect (~1.0 across all four dims), about's candidate is absent.
    grade(
        fixture_dirs["multipage"],
        fixture_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    # Mean of a ~1.0 page and a 0.0 missing page lands at (just) 0.5; the
    # missing page halves what a single perfect page would have scored.
    assert 0.45 < reward["reward"] <= 0.5


def test_reward_details_reports_per_page_and_missing(fixture_dirs, tmp_path):
    grade(
        fixture_dirs["multipage"],
        fixture_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    pages = details["pages"]
    assert pages["home"]["present"] is True
    assert pages["home"]["structure"] > 0.99
    assert pages["home"]["color"] > 0.99
    assert pages["home"]["design_judge"] == 1.0
    assert pages["about"]["present"] is False
    # Every dimension is zeroed for a missing page, not just structure.
    assert pages["about"]["structure"] == 0.0
    assert pages["about"]["color"] == 0.0
    assert pages["about"]["design_judge"] == 0.0


def test_reward_details_records_judge_sub_scores(fixture_dirs, tmp_path):
    judge = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    grade(
        fixture_dirs["perfect"], fixture_dirs["reference"], HOME_ONLY, tmp_path, judge
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    sub = details["pages"]["home"]["design_judge_sub_scores"]
    assert sub == {
        "layout_alignment": 0.8,
        "color_palette": 0.6,
        "typography": 1.0,
        "content_completeness": 0.4,
    }
