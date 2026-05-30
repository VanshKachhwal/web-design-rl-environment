"""Behavioral tests for the pure aggregation of per-page scores into reward.

Assert the external shape and math of the reward payload, never internals.
"""

import pytest

from webdesign_rl.grade.aggregate import aggregate

ALL = ("structure", "color", "content", "design_judge")


def _page(value):
    """A page whose every dimension scores ``value``."""
    return {dim: value for dim in ALL}


def test_single_page_reward_equals_mean_of_its_dimensions():
    payload = aggregate({"home": _page(0.8)})
    assert payload["reward"] == pytest.approx(0.8)
    for dim in ALL:
        assert payload[dim] == pytest.approx(0.8)


def test_multipage_reward_is_mean_of_page_scores():
    payload = aggregate({"home": _page(0.9), "about": _page(0.5)})
    assert payload["reward"] == pytest.approx(0.7)
    for dim in ALL:
        assert payload[dim] == pytest.approx(0.7)


def test_missing_required_page_contributes_zero():
    payload = aggregate({"home": _page(1.0), "about": None})
    # One perfect page, one missing page => mean of 1.0 and 0.0 per dimension.
    assert payload["reward"] == pytest.approx(0.5)
    for dim in ALL:
        # The missing page zeros every dimension, not just the pixel terms.
        assert payload[dim] == pytest.approx(0.5)


def test_page_score_is_mean_of_all_four_terms():
    payload = aggregate(
        {"home": {"structure": 0.8, "color": 0.4, "content": 0.6, "design_judge": 0.2}}
    )
    # Each term flows through as its own averaged dimension...
    assert payload["structure"] == pytest.approx(0.8)
    assert payload["color"] == pytest.approx(0.4)
    assert payload["content"] == pytest.approx(0.6)
    assert payload["design_judge"] == pytest.approx(0.2)
    # ...and the page score (and so reward) is the mean of the page's terms.
    assert payload["reward"] == pytest.approx((0.8 + 0.4 + 0.6 + 0.2) / 4)
