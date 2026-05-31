"""Unit tests for the eval report harvest + plot-data core (EP-03).

The harvest turns a saved Harbor job dir into a normalized scores object; the
per-trial ``verifier/reward.json`` + ``reward-details.json`` files are the term
source of truth (the job-level eval key is dynamic, so we never parse it). These
tests build a *tiny synthetic* job dir under ``tmp_path`` so they are fast and
independent of the real ``jobs/opus47-004/`` job.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from webdesign_rl.eval import aggregate_results as agg

REPO = Path(__file__).resolve().parent.parent


def _load_report_module():
    """Import ``scripts/report.py`` (not a package) by path."""
    spec = importlib.util.spec_from_file_location(
        "report_cli", REPO / "scripts" / "report.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["report_cli"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- synthetic fixture job dir ------------------------------------------------


def _write_trial(job_dir, trial_id, reward_payload, pages, task_path="out/eval/t/task"):
    """Write one ``task__<id>/`` with verifier reward files + a trial result."""
    tdir = job_dir / f"task__{trial_id}"
    (tdir / "verifier").mkdir(parents=True)
    (tdir / "verifier" / "reward.json").write_text(json.dumps(reward_payload))
    (tdir / "verifier" / "reward-details.json").write_text(
        json.dumps({"reward": reward_payload, "pages": pages})
    )
    (tdir / "result.json").write_text(json.dumps({"config": {
        "task": {"path": task_path},
        # Real jobs record agent/executor on the TRIAL result, not the job one.
        "agent": {"name": "claude-code", "model_name": "claude-opus-4-7"},
        "environment": {"type": "modal"},
    }}))


def _page(present=True, structure=0.7, color=0.9, content=0.5, design_judge=0.6,
          sub=None):
    return {
        "present": present,
        "structure": structure,
        "color": color,
        "content": content,
        "design_judge": design_judge,
        "design_judge_sub_scores": sub or {
            "layout_alignment": 0.7,
            "color_palette": 0.8,
            "typography": 0.7,
            "content_completeness": 0.6,
        },
    }


@pytest.fixture
def synthetic_job(tmp_path):
    """A 2-trial job dir with a *dynamic* eval key and a sibling seed.json."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()

    # Real layout: config.task.path -> ".../eval/<id>/task"; seed.json lives in
    # the sibling ".../eval/<id>/site/seed.json".
    evaldir = tmp_path / "eval004"
    site = evaldir / "site"
    site.mkdir(parents=True)
    (site / "seed.json").write_text(json.dumps({
        "archetype": "local-service",
        "aesthetic": "luxury-serif",
        "complexity": "med",
        "seed_tuple": ["local-service", "luxury-serif", "med"],
    }))
    task_path = str(evaldir / "task")

    # result.json: note the DYNAMIC eval key — harvest must not parse it.
    (job_dir / "result.json").write_text(json.dumps({
        "started_at": "2026-05-31T16:00:00.000000",
        "finished_at": "2026-05-31T16:30:00.000000",
        "n_total_trials": 2,
        "stats": {
            "evals": {
                "claude-code__claude-opus-4-7__adhoc": {
                    "n_trials": 2,
                    "metrics": [{"reward": 0.999}],  # WRONG on purpose
                }
            },
            "n_input_tokens": 1000,
            "n_output_tokens": 200,
            "cost_usd": 12.5,
        },
    }))

    _write_trial(
        job_dir, "AAA",
        {"structure": 0.7, "color": 0.9, "content": 0.5,
         "design_judge": 0.6, "reward": 0.675},
        {"index": _page(content=0.5), "about": _page(content=0.3)},
        task_path=task_path,
    )
    _write_trial(
        job_dir, "BBB",
        {"structure": 0.8, "color": 0.92, "content": 0.6,
         "design_judge": 0.7, "reward": 0.755},
        {"index": _page(content=0.6), "about": _page(content=0.4)},
        task_path=task_path,
    )
    return job_dir


# --- harvest: per-trial terms from the per-trial files ------------------------


def test_harvest_reads_per_trial_reward_and_terms(synthetic_job):
    scores = agg.harvest(synthetic_job)

    trials = {t["trial_id"]: t for t in scores["trials"]}
    assert set(trials) == {"AAA", "BBB"}
    aaa = trials["AAA"]
    # Source of truth is the per-trial reward.json, NOT the job-level metrics.
    assert aaa["reward"] == pytest.approx(0.675)
    assert aaa["structure"] == pytest.approx(0.7)
    assert aaa["color"] == pytest.approx(0.9)
    assert aaa["content"] == pytest.approx(0.5)
    assert aaa["design_judge"] == pytest.approx(0.6)


def test_harvest_reads_per_page_terms_and_sub_scores(synthetic_job):
    scores = agg.harvest(synthetic_job)
    aaa = next(t for t in scores["trials"] if t["trial_id"] == "AAA")

    assert set(aaa["pages"]) == {"index", "about"}
    about = aaa["pages"]["about"]
    assert about["present"] is True
    assert about["content"] == pytest.approx(0.3)
    assert about["color"] == pytest.approx(0.9)
    # Judge sub-scores are carried through under "sub_scores".
    assert about["sub_scores"]["content_completeness"] == pytest.approx(0.6)
    assert about["sub_scores"]["layout_alignment"] == pytest.approx(0.7)


def test_harvest_run_metadata(synthetic_job):
    meta = agg.harvest(synthetic_job)["meta"]

    assert meta["model"] == "claude-opus-4-7"
    assert meta["agent"] == "claude-code"
    assert meta["executor"] == "modal"
    assert meta["n_trials"] == 2
    assert meta["total_cost_usd"] == pytest.approx(12.5)
    assert meta["total_input_tokens"] == 1000
    assert meta["total_output_tokens"] == 200
    assert meta["started_at"] == "2026-05-31T16:00:00.000000"
    assert meta["finished_at"] == "2026-05-31T16:30:00.000000"
    # 16:00 -> 16:30 is 1800 seconds of wall-clock.
    assert meta["wall_clock_sec"] == pytest.approx(1800.0)


def test_write_scores_json_roundtrips(synthetic_job, tmp_path):
    scores = agg.harvest(synthetic_job)
    out = tmp_path / "out"
    out.mkdir()

    agg.write_scores(scores, out)

    reloaded = json.loads((out / "scores.json").read_text())
    assert reloaded == scores


def test_write_scores_csv_is_long_form(synthetic_job, tmp_path):
    """One row per (trial, page, term); a ``__all__`` page holds trial-level terms."""
    import csv

    scores = agg.harvest(synthetic_job)
    out = tmp_path / "out"
    out.mkdir()

    agg.write_scores(scores, out)

    with open(out / "scores.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert {"trial_id", "page", "term", "value"} <= set(rows[0])
    # The trial-level aggregate terms are exported under the "__all__" sentinel.
    agg_content = [
        r for r in rows
        if r["trial_id"] == "AAA" and r["page"] == "__all__" and r["term"] == "content"
    ]
    assert len(agg_content) == 1
    assert float(agg_content[0]["value"]) == pytest.approx(0.5)
    # Per-page rows are present too.
    page_content = [
        r for r in rows
        if r["trial_id"] == "AAA" and r["page"] == "about" and r["term"] == "content"
    ]
    assert len(page_content) == 1
    assert float(page_content[0]["value"]) == pytest.approx(0.3)


def test_harvest_seed_tuple_from_task_seed_json(synthetic_job):
    meta = agg.harvest(synthetic_job)["meta"]

    assert meta["archetype"] == "local-service"
    assert meta["aesthetic"] == "luxury-serif"
    assert meta["complexity"] == "med"
    assert meta["seed_tuple"] == ["local-service", "luxury-serif", "med"]


# --- pure plot-data computations ----------------------------------------------


def test_reward_series_is_one_value_per_trial(synthetic_job):
    scores = agg.harvest(synthetic_job)
    series = agg.reward_series(scores)
    assert sorted(series) == pytest.approx([0.675, 0.755])


def test_summary_stats(synthetic_job):
    scores = agg.harvest(synthetic_job)
    s = agg.summary_stats(agg.reward_series(scores))

    assert s["mean"] == pytest.approx(0.715)
    assert s["median"] == pytest.approx(0.715)
    assert s["min"] == pytest.approx(0.675)
    assert s["max"] == pytest.approx(0.755)
    # Population std of [0.675, 0.755] = 0.04.
    assert s["std"] == pytest.approx(0.04)


def test_per_term_distributions(synthetic_job):
    scores = agg.harvest(synthetic_job)
    dists = agg.per_term_distributions(scores)

    assert set(dists) == {"structure", "color", "content", "design_judge"}
    assert sorted(dists["content"]) == pytest.approx([0.5, 0.6])
    assert sorted(dists["structure"]) == pytest.approx([0.7, 0.8])


def test_per_term_mean_std(synthetic_job):
    scores = agg.harvest(synthetic_job)
    ms = agg.per_term_mean_std(scores)

    assert ms["content"]["mean"] == pytest.approx(0.55)
    assert ms["content"]["std"] == pytest.approx(0.05)
    assert ms["color"]["mean"] == pytest.approx(0.91)


def test_per_page_term_matrix(synthetic_job):
    """Mean across trials of each (page, term) cell."""
    scores = agg.harvest(synthetic_job)
    matrix = agg.per_page_term_matrix(scores)

    assert set(matrix["pages"]) == {"index", "about"}
    assert matrix["terms"] == ["structure", "color", "content", "design_judge"]
    # content on "about": mean of 0.3 (AAA) and 0.4 (BBB) = 0.35.
    cell = matrix["values"][matrix["pages"].index("about")][
        matrix["terms"].index("content")
    ]
    assert cell == pytest.approx(0.35)
    # content on "index": mean of 0.5 and 0.6 = 0.55.
    cell_idx = matrix["values"][matrix["pages"].index("index")][
        matrix["terms"].index("content")
    ]
    assert cell_idx == pytest.approx(0.55)


# --- end-to-end: the report shell writes a self-contained report --------------


def test_build_report_writes_self_contained_html_and_sidecars(synthetic_job, tmp_path):
    """Pointed at a job dir, build_report writes scores.json/csv + report.html.

    ``report.html`` must be self-contained: it embeds its plot images (no sibling
    PNG assets) and renders items 1-5 (provenance, score table, distributions,
    per-term bars, per-page heatmap).
    """
    report = _load_report_module()
    out = tmp_path / "report_out"

    report.build_report(synthetic_job, out)

    assert (out / "scores.json").exists()
    assert (out / "scores.csv").exists()
    html_path = out / "report.html"
    assert html_path.exists()

    # Self-contained: images embedded as base64 data URIs, no sibling PNG files.
    html = html_path.read_text()
    # Three plots (items 3, 4, 5) all embedded as base64 PNG data URIs.
    assert html.count("data:image/png;base64,") == 3
    assert not list(out.glob("*.png"))

    # Item 1 provenance (seed tuple + model + executor) rendered as text.
    assert "local-service" in html
    assert "claude-opus-4-7" in html
    assert "modal" in html
    # Item 2 score table: every trial id + a summary row + the term names.
    assert "AAA" in html and "BBB" in html
    assert "summary" in html
    assert "structure" in html and "content" in html
    # Section headings for items 1-5 are all present.
    for n in range(1, 6):
        assert f">{n}." in html
