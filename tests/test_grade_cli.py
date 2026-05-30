"""Behavioral tests for the grader CLI entrypoint (``python -m webdesign_rl.grade``).

The CLI is what the packaged Harbor task's ``tests/test.sh`` invokes: it takes a
candidate directory, a reference directory, a ``page_map`` JSON file, and an
output directory, renders + grades, and writes ``reward.json`` into the output
directory. ``--no-judge`` selects the fully-deterministic mode (no VLM call, no
API key, no egress) used as the primary oracle validation.

These tests drive the CLI exactly as ``test.sh`` would — as a subprocess /
``main(argv)`` call — and assert only the written ``reward.json``.
"""

import json
from pathlib import Path

from webdesign_rl.grade.__main__ import main

FIXTURES = Path(__file__).parent / "fixtures"


def _write_page_map(tmp_path, page_map):
    path = tmp_path / "page_map.json"
    path.write_text(json.dumps(page_map))
    return path


def test_no_judge_cli_scores_oracle_candidate_near_one(site_dirs, tmp_path):
    # The "perfect" candidate is the exact HTML the reference PNG was rendered
    # from, so the three deterministic terms (and the reward) land at ~1.0 with
    # no judge involved.
    page_map = {"home": {"screenshot": "home.png", "expected_file": "index.html"}}
    page_map_path = _write_page_map(tmp_path, page_map)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "--candidate", str(site_dirs["perfect"]),
            "--reference", str(site_dirs["reference"]),
            "--page-map", str(page_map_path),
            "--out", str(out_dir),
            "--no-judge",
        ]
    )

    assert exit_code == 0
    reward = json.loads((out_dir / "reward.json").read_text())
    # Deterministic-only: design_judge is dropped, the reward is the mean of the
    # three deterministic terms.
    assert set(reward) == {"reward", "structure", "color", "content"}
    assert reward["reward"] > 0.99


def test_no_judge_cli_missing_page_drags_reward(site_dirs, tmp_path):
    # home is the oracle (~1.0); about.html is absent so it scores 0 across the
    # three deterministic dims. The reward halves — and no judge ever runs.
    page_map = {
        "home": {"screenshot": "home.png", "expected_file": "index.html"},
        "about": {"screenshot": "home.png", "expected_file": "about.html"},
    }
    page_map_path = _write_page_map(tmp_path, page_map)
    out_dir = tmp_path / "out"

    main(
        [
            "--candidate", str(site_dirs["missing"]),
            "--reference", str(site_dirs["reference"]),
            "--page-map", str(page_map_path),
            "--out", str(out_dir),
            "--no-judge",
        ]
    )

    reward = json.loads((out_dir / "reward.json").read_text())
    assert 0.45 < reward["reward"] <= 0.5
    # The per-page breakdown is still written, marking the absent page.
    details = json.loads((out_dir / "reward-details.json").read_text())
    assert details["pages"]["about"]["present"] is False


def test_reference_site_is_rendered_in_process(tmp_path):
    # When the reference is given as a *site* directory (HTML), the grader renders
    # it in-process instead of reading committed PNGs. This is the deterministic,
    # host-independent reference: candidate and reference render with the SAME
    # fonts/engine, so the oracle (identical HTML) hits an exact ceiling of ~1.0
    # across every deterministic term — no host/container font mismatch.
    reference_site = FIXTURES / "site5_reference"
    page_map = {
        "home": {"screenshot": "home.png", "expected_file": "index.html"},
        "about": {"screenshot": "about.png", "expected_file": "about.html"},
    }
    page_map_path = _write_page_map(tmp_path, page_map)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "--candidate", str(reference_site),
            "--reference-site", str(reference_site),
            "--page-map", str(page_map_path),
            "--out", str(out_dir),
            "--no-judge",
        ]
    )

    assert exit_code == 0
    reward = json.loads((out_dir / "reward.json").read_text())
    assert reward["structure"] > 0.999
    assert reward["color"] > 0.999
    assert reward["content"] > 0.999
    assert reward["reward"] > 0.999
