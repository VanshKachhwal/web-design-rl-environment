"""Behavioral tests for the pure aggregation of per-page scores into reward.

Assert the external shape and math of the reward payload, never internals.
"""

import pytest

from webdesign_rl.grade.aggregate import aggregate


def test_single_page_reward_equals_mean_of_its_dimensions():
    payload = aggregate({"home": {"structure": 0.8, "color": 0.8, "content": 0.8}})
    assert payload["reward"] == pytest.approx(0.8)
    assert payload["structure"] == 0.8
    assert payload["color"] == 0.8
    assert payload["content"] == 0.8


def test_multipage_reward_is_mean_of_page_scores():
    payload = aggregate(
        {
            "home": {"structure": 0.9, "color": 0.9, "content": 0.9},
            "about": {"structure": 0.5, "color": 0.5, "content": 0.5},
        }
    )
    assert payload["reward"] == 0.7
    assert payload["structure"] == 0.7
    assert payload["color"] == 0.7
    assert payload["content"] == 0.7


def test_missing_required_page_contributes_zero():
    payload = aggregate(
        {"home": {"structure": 1.0, "color": 1.0, "content": 1.0}, "about": None}
    )
    # One perfect page, one missing page => mean of 1.0 and 0.0 per dimension.
    assert payload["reward"] == 0.5
    assert payload["structure"] == 0.5
    assert payload["color"] == 0.5
    assert payload["content"] == 0.5


def test_payload_carries_color_dimension():
    payload = aggregate({"home": {"structure": 0.8, "color": 0.4, "content": 0.6}})
    # color flows through as its own averaged dimension.
    assert payload["color"] == 0.4
    # Page score (and so reward) is the mean of the page's terms.
    assert payload["reward"] == pytest.approx(0.6)


def test_payload_carries_content_dimension():
    payload = aggregate({"home": {"structure": 0.9, "color": 0.6, "content": 0.3}})
    # content flows through as its own averaged dimension.
    assert payload["content"] == 0.3
    # Page score (and so reward) is the mean of all three terms.
    assert payload["reward"] == pytest.approx(0.6)
