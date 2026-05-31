"""End-to-end behavioral tests for the grade() orchestrator (live-render path).

Since issue 05 the grader takes a candidate *directory of HTML/CSS*: it renders
the candidate itself (headless Chromium over a local HTTP server) and compares
the rendered screenshot to a committed reference PNG. These tests drive the full
spine (render -> metric -> aggregate -> write) and assert only the written reward
outputs. The judge term is pinned with a ``StubJudgeClient`` so there are no live
API calls.
"""

import json
import logging

import pytest
from PIL import Image

from webdesign_rl.grade.grader import grade
from webdesign_rl.grade.judge import StubJudgeClient


class RaisingJudgeClient:
    """A judge client whose scoring blows up — for the fail-loud path."""

    def __init__(self, exc):
        self._exc = exc

    def score(self, reference_img, candidate_img):
        raise self._exc

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
    # The four per-term breakdowns are read off grade()'s return value (the
    # in-process flat dict); on disk reward.json holds only the scalar aggregate.
    reward = grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    # The perfect candidate is the same HTML the reference PNG was rendered from,
    # so the deterministic dims land at ~1.0.
    assert reward["structure"] > 0.99
    assert reward["color"] > 0.99
    assert reward["content"] > 0.99
    assert reward["design_judge"] == 1.0
    assert reward["reward"] > 0.99


def test_reward_return_value_has_expected_keys_and_ranges(site_dirs, tmp_path):
    reward = grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
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
        return grade(
            site_dirs[name], site_dirs["reference"], HOME_ONLY, out, _perfect_judge()
        )

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
    reward = grade(
        site_dirs["perfect"], site_dirs["reference"], HOME_ONLY, tmp_path, judge
    )
    assert reward["design_judge"] == 0.7


def test_missing_required_page_drags_reward_to_half(site_dirs, tmp_path):
    # home is perfect (~1.0 across all four dims); about.html is absent from the
    # candidate directory, so it renders to nothing and scores 0.
    reward = grade(
        site_dirs["missing"],
        site_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
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


def test_grade_persists_rendered_candidate_pngs(site_dirs, tmp_path):
    # The exact candidate screenshots the grader scored are written into a
    # renders/ subdir of the output dir, keyed by the page identity, so a report
    # can pair each render with its reference.
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    render = tmp_path / "renders" / "home.png"
    assert render.exists()
    # It is a valid image (the rendered candidate page), not an empty file.
    with Image.open(render) as img:
        assert img.size[0] > 0 and img.size[1] > 0


def test_grade_persists_reference_renders_keyed_by_page(site_dirs, tmp_path):
    # Symmetric to the candidate renders: the exact reference images the grader
    # scored against are written into reference_renders/, keyed by PAGE NAME (not
    # the screenshot filename), so a report loads reference + candidate uniformly.
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    ref_render = tmp_path / "reference_renders" / "home.png"
    assert ref_render.exists()
    with Image.open(ref_render) as img:
        assert img.size[0] > 0 and img.size[1] > 0


def test_grade_persists_reference_render_for_absent_candidate_page(
    site_dirs, tmp_path
):
    # about.html is absent from the candidate dir, but its reference render is
    # still persisted (the report can show reference-vs-blank for the dropped
    # page) — so the reference save happens before the missing-page continue.
    grade(
        site_dirs["missing"],
        site_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    refs = tmp_path / "reference_renders"
    assert (refs / "home.png").exists()
    assert (refs / "about.png").exists()


def test_grade_opt_out_writes_no_renders_but_still_grades(site_dirs, tmp_path):
    # save_renders=False suppresses the PNGs entirely while grading proceeds
    # normally (reward.json is still written) — for BOTH candidate and reference.
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
        save_renders=False,
    )
    assert not (tmp_path / "renders").exists()
    assert not (tmp_path / "reference_renders").exists()
    reward = _load_reward(tmp_path)
    assert reward["reward"] > 0.99


def test_grade_skips_render_for_absent_candidate_page(site_dirs, tmp_path):
    # about.html is absent from the candidate dir (a missing/zero-scored page):
    # persistence simply skips it (no PNG, no crash) while the present page's
    # render is still written.
    grade(
        site_dirs["missing"],
        site_dirs["reference"],
        HOME_AND_ABOUT,
        tmp_path,
        _perfect_judge(),
    )
    renders = tmp_path / "renders"
    assert (renders / "home.png").exists()
    assert not (renders / "about.png").exists()


def test_grade_persists_renders_in_deterministic_only_mode(site_dirs, tmp_path):
    # Renders are independent of the judge: deterministic-only grading
    # (judge_client=None) persists the same candidate PNGs.
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        None,
    )
    assert (tmp_path / "renders" / "home.png").exists()


def test_reward_json_on_disk_is_single_canonical_scalar(site_dirs, tmp_path):
    # On disk, reward.json carries exactly one unambiguous metric: the canonical
    # aggregate `reward` (a float). The four per-term breakdowns live in
    # reward-details.json, not here — so Harbor sees one, unambiguous metric.
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    reward = _load_reward(tmp_path)
    assert set(reward.keys()) == {"reward"}
    assert isinstance(reward["reward"], float)


def test_reward_details_on_disk_keeps_full_five_key_breakdown(site_dirs, tmp_path):
    # reward-details.json is unchanged: top-level "reward" is the full five-key
    # term dict (four terms + the aggregate), plus per-page terms under "pages".
    grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    assert set(details["reward"].keys()) == {
        "reward",
        "structure",
        "color",
        "content",
        "design_judge",
    }
    assert "pages" in details


def test_grade_return_value_keeps_full_four_term_breakdown(site_dirs, tmp_path):
    # The in-process return value is the full flat dict (callers/tests read the
    # four terms off it); only the on-disk reward.json is slimmed.
    reward = grade(
        site_dirs["perfect"],
        site_dirs["reference"],
        HOME_ONLY,
        tmp_path,
        _perfect_judge(),
    )
    assert set(reward.keys()) == {
        "reward",
        "structure",
        "color",
        "content",
        "design_judge",
    }


def test_judge_failure_propagates_and_writes_no_reward(site_dirs, tmp_path):
    # design_judge is an integral quarter of the reward: an unexpected judge
    # failure must NOT be swallowed into a degraded 3-term reward. grade() must
    # re-raise (the trial errors loudly) and write no reward.json.
    judge = RaisingJudgeClient(RuntimeError("judge exploded"))
    with pytest.raises(RuntimeError, match="judge exploded"):
        grade(
            site_dirs["perfect"],
            site_dirs["reference"],
            HOME_ONLY,
            tmp_path,
            judge,
        )
    assert not (tmp_path / "reward.json").exists()
    assert not (tmp_path / "reward-details.json").exists()


def test_judge_failure_logs_page_name(site_dirs, tmp_path, caplog):
    # The fail-loud catch adds page-context diagnostics: the failing page name
    # is logged before the error re-raises, so the operator knows which page.
    judge = RaisingJudgeClient(RuntimeError("judge exploded"))
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            grade(
                site_dirs["perfect"],
                site_dirs["reference"],
                HOME_ONLY,
                tmp_path,
                judge,
            )
    assert "home" in caplog.text
