"""Behavioral tests for the pure aggregation of per-page scores into reward.

Assert the external shape and math of the reward payload, never internals.
"""

import pytest

from webdesign_rl.grade.aggregate import aggregate


def test_single_page_reward_equals_mean_of_its_dimensions():
    payload = aggregate(
        {"home": {"structure": 0.8, "color": 0.8, "design_judge": 0.8}}
    )
    assert payload["reward"] == pytest.approx(0.8)
    assert payload["structure"] == 0.8
    assert payload["color"] == 0.8
    assert payload["design_judge"] == 0.8


def test_multipage_reward_is_mean_of_page_scores():
    payload = aggregate(
        {
            "home": {"structure": 0.9, "color": 0.9, "design_judge": 0.9},
            "about": {"structure": 0.5, "color": 0.5, "design_judge": 0.5},
        }
    )
    assert payload["reward"] == 0.7
    assert payload["structure"] == 0.7
    assert payload["color"] == 0.7
    assert payload["design_judge"] == 0.7


def test_missing_required_page_contributes_zero():
    payload = aggregate(
        {
            "home": {"structure": 1.0, "color": 1.0, "design_judge": 1.0},
            "about": None,
        }
    )
    # One perfect page, one missing page => mean of 1.0 and 0.0 per dimension.
    assert payload["reward"] == 0.5
    assert payload["structure"] == 0.5
    assert payload["color"] == 0.5
    # The missing page zeros design_judge too, not just the pixel terms.
    assert payload["design_judge"] == 0.5


def test_page_score_is_mean_of_all_four_terms():
    payload = aggregate(
        {"home": {"structure": 0.8, "color": 0.4, "design_judge": 0.6}}
    )
    # Each term flows through as its own averaged dimension...
    assert payload["color"] == 0.4
    assert payload["design_judge"] == 0.6
    # ...and the page score (and so reward) is the mean of the page's terms.
    assert payload["reward"] == pytest.approx((0.8 + 0.4 + 0.6) / 3)
