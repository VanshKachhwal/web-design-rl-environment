"""End-to-end behavioral tests for the grade() orchestrator.

These exercise the full spine (load -> metric -> aggregate -> write) on committed
PNG fixtures and assert only the written reward outputs.
"""

import json

from webdesign_rl.grade.grader import grade

HOME_ONLY = {"home": {"screenshot": "home.png", "expected_file": "home.png"}}
HOME_AND_ABOUT = {
    "home": {"screenshot": "home.png", "expected_file": "home.png"},
    "about": {"screenshot": "about.png", "expected_file": "about.png"},
}


def _load_reward(out_dir):
    return json.loads((out_dir / "reward.json").read_text())


def test_perfect_candidate_scores_all_dimensions_near_one(fixture_dirs, tmp_path):
    grade(fixture_dirs["perfect"], fixture_dirs["reference"], HOME_ONLY, tmp_path)
    reward = _load_reward(tmp_path)
    assert reward["structure"] > 0.99
    assert reward["color"] > 0.99
    # A byte-identical candidate has identical OCR text, so content is ~1.0 too.
    assert reward["content"] > 0.99
    assert reward["reward"] > 0.99


def test_reward_json_has_expected_keys_and_ranges(fixture_dirs, tmp_path):
    grade(fixture_dirs["perfect"], fixture_dirs["reference"], HOME_ONLY, tmp_path)
    reward = _load_reward(tmp_path)
    # Flat object: the scalar reward plus the structure, color and content dims.
    assert set(reward.keys()) == {"reward", "structure", "color", "content"}
    for value in reward.values():
        assert isinstance(value, float)
        assert 0.0 <= value <= 1.0


def test_worse_candidates_score_lower(fixture_dirs, tmp_path):
    def reward_for(name):
        out = tmp_path / name
        grade(fixture_dirs[name], fixture_dirs["reference"], HOME_ONLY, out)
        return _load_reward(out)["reward"]

    perfect = reward_for("perfect")
    blurred = reward_for("blurred")
    different = reward_for("different")
    assert perfect > blurred > different


def test_missing_required_page_drags_reward_to_half(fixture_dirs, tmp_path):
    # home is perfect (~1.0), about's candidate file is absent (0.0).
    grade(
        fixture_dirs["multipage"], fixture_dirs["reference"], HOME_AND_ABOUT, tmp_path
    )
    reward = _load_reward(tmp_path)
    # Mean of a ~1.0 page and a 0.0 missing page lands at (just) 0.5; the
    # missing page halves what a single perfect page would have scored.
    assert 0.45 < reward["reward"] <= 0.5


def test_reward_details_reports_per_page_and_missing(fixture_dirs, tmp_path):
    grade(
        fixture_dirs["multipage"], fixture_dirs["reference"], HOME_AND_ABOUT, tmp_path
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    pages = details["pages"]
    assert pages["home"]["present"] is True
    assert pages["home"]["structure"] > 0.99
    assert pages["home"]["color"] > 0.99
    assert pages["home"]["content"] > 0.99
    assert pages["about"]["present"] is False
    # Every dimension is zeroed for a missing page, not just structure.
    assert pages["about"]["structure"] == 0.0
    assert pages["about"]["color"] == 0.0
    assert pages["about"]["content"] == 0.0
