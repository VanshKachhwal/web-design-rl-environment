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
from PIL import Image

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


def test_harvest_reads_terms_from_details_with_slim_reward_json(tmp_path):
    """A new-format job writes a SLIM one-key reward.json; terms come from details.

    After EP-06 the grader writes ``reward.json`` = ``{"reward": float}`` only.
    The four per-term breakdowns are sourced from ``reward-details.json["reward"]``
    (which still carries the full five-key dict), so the harvested trial record is
    identical to the old five-key-reward.json job — no back-compat branch.
    """
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "result.json").write_text(json.dumps({
        "started_at": "2026-05-31T16:00:00.000000",
        "finished_at": "2026-05-31T16:30:00.000000",
        "n_total_trials": 1,
        "stats": {},
    }))

    tdir = job_dir / "task__SLIM"
    (tdir / "verifier").mkdir(parents=True)
    full_terms = {"structure": 0.7, "color": 0.9, "content": 0.5,
                  "design_judge": 0.6, "reward": 0.675}
    # On disk reward.json is the slimmed single scalar (EP-06).
    (tdir / "verifier" / "reward.json").write_text(json.dumps({"reward": 0.675}))
    # reward-details.json still embeds the full five-key dict under "reward".
    (tdir / "verifier" / "reward-details.json").write_text(json.dumps({
        "reward": full_terms,
        "pages": {"index": _page(content=0.5)},
    }))
    (tdir / "result.json").write_text(json.dumps({"config": {}}))

    scores = agg.harvest(job_dir)
    trial = scores["trials"][0]
    assert trial["trial_id"] == "SLIM"
    assert trial["reward"] == pytest.approx(0.675)
    assert trial["structure"] == pytest.approx(0.7)
    assert trial["color"] == pytest.approx(0.9)
    assert trial["content"] == pytest.approx(0.5)
    assert trial["design_judge"] == pytest.approx(0.6)


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


# --- pure selection logic for the visual-evidence galleries (EP-04) -----------


def test_per_metric_extrema_picks_best_and_worst_trial_page(synthetic_job):
    """For each term, the (trial, page) cell with the highest/lowest score.

    Extremes are at the trial x page level (a concrete screenshot), not a
    whole-site average. In the fixture, content ranges from 0.3 (AAA/about) up
    to 0.6 (BBB/index).
    """
    scores = agg.harvest(synthetic_job)
    extrema = agg.per_metric_extrema(scores)

    assert set(extrema) == {"structure", "color", "content", "design_judge"}

    content = extrema["content"]
    assert content["best"]["trial_id"] == "BBB"
    assert content["best"]["page"] == "index"
    assert content["best"]["score"] == pytest.approx(0.6)
    assert content["worst"]["trial_id"] == "AAA"
    assert content["worst"]["page"] == "about"
    assert content["worst"]["score"] == pytest.approx(0.3)
    # The term's score range is annotated so a reader can gauge the spread.
    assert content["range"] == pytest.approx([0.3, 0.6])


def test_per_metric_extrema_low_variance_term_reads_as_uniform(synthetic_job):
    """A uniformly-scored term has best == worst and a zero-width range.

    Color is 0.9 on every page in the fixture; the range annotation lets the
    report show "uniformly good" rather than implying the pair carries signal.
    """
    scores = agg.harvest(synthetic_job)
    color = agg.per_metric_extrema(scores)["color"]

    assert color["best"]["score"] == pytest.approx(0.9)
    assert color["worst"]["score"] == pytest.approx(0.9)
    assert color["range"] == pytest.approx([0.9, 0.9])


def test_per_metric_extrema_skips_absent_pages():
    """An absent page carries no render, so it never wins an extremum."""
    scores = {
        "terms": list(agg.TERMS),
        "trials": [{
            "trial_id": "T", "reward": 0.5,
            "structure": 0.5, "color": 0.5, "content": 0.5, "design_judge": 0.5,
            "pages": {
                # absent page has a 0.0 that must NOT become the "worst" render
                "missing": {"present": False, "structure": 0.0, "color": 0.0,
                            "content": 0.0, "design_judge": 0.0, "sub_scores": {}},
                "index": {"present": True, "structure": 0.4, "color": 0.4,
                          "content": 0.4, "design_judge": 0.4, "sub_scores": {}},
            },
        }],
    }
    struct = agg.per_metric_extrema(scores)["structure"]
    assert struct["worst"]["page"] == "index"
    assert struct["worst"]["score"] == pytest.approx(0.4)


def test_best_overall_trial_is_highest_reward(synthetic_job):
    """The best-overall trial is the single highest-aggregate-reward trial."""
    scores = agg.harvest(synthetic_job)
    # BBB has reward 0.755 vs AAA's 0.675.
    assert agg.best_overall_trial(scores) == "BBB"


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


# --- visual-evidence galleries (items 6-7) over a with-renders fixture --------


def _solid_png(path, color, size=(8, 6)):
    """Write a tiny solid-color PNG so the gallery has real pixels to embed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


@pytest.fixture
def synthetic_job_with_renders(synthetic_job):
    """Extend the 2-trial job with persisted ``verifier/renders/`` + a task.

    EP-01's grader writes each candidate page to
    ``task__<id>/verifier/renders/<page>.png`` (page-map key), and the task bakes
    the reference screenshots it compared against under
    ``<task>/tests/reference_site/<screenshot>.png`` with a ``tests/page_map.json``
    mapping page -> screenshot. ``jobs/opus47-004`` predates renders, so the
    gallery is exercised against this fixture instead.
    """
    job_dir = synthetic_job
    # Each present page gets a tiny candidate render, keyed by the page-map key.
    page_color = {
        "AAA": {"index": (200, 30, 30), "about": (30, 200, 30)},
        "BBB": {"index": (30, 30, 200), "about": (200, 200, 30)},
    }
    for trial_id, pages in page_color.items():
        renders = job_dir / f"task__{trial_id}" / "verifier" / "renders"
        for page, color in pages.items():
            _solid_png(renders / f"{page}.png", color)

    # The task baked the reference screenshots (mapped via page_map by screenshot
    # filename, which need NOT equal the page key).
    task_path = Path(json.loads(
        (job_dir / "task__AAA" / "result.json").read_text()
    )["config"]["task"]["path"])
    page_map = {
        "index": {"screenshot": "index.png", "expected_file": "index.html"},
        "about": {"screenshot": "about_ref.png", "expected_file": "about.html"},
    }
    (task_path / "tests").mkdir(parents=True, exist_ok=True)
    (task_path / "tests" / "page_map.json").write_text(json.dumps(page_map))
    ref_site = task_path / "tests" / "reference_site"
    _solid_png(ref_site / "index.png", (10, 10, 10))
    _solid_png(ref_site / "about_ref.png", (240, 240, 240))
    return job_dir


def test_report_renders_visual_galleries_self_contained(
    synthetic_job_with_renders, tmp_path
):
    """Items 6-7: per-metric best/worst + best-overall galleries, all embedded.

    Item 6 is a reference|best|worst triple per term (4 terms); item 7 pairs the
    best-overall trial's render with the reference for every page. Every image is
    base64-embedded so report.html stays a single self-contained file.
    """
    report = _load_report_module()
    out = tmp_path / "report_out"

    report.build_report(synthetic_job_with_renders, out)

    html = (out / "report.html").read_text()

    # Items 6 and 7 have section headings.
    assert ">6." in html
    assert ">7." in html

    # Item 6: a reference|best|worst triple for EACH of the four terms.
    for term in ("structure", "color", "content", "design_judge"):
        assert term in html
    assert html.count("reference") >= 4  # one labelled reference per term row
    assert "best" in html and "worst" in html
    # Scores are labelled and the term range is annotated (content spans 0.3-0.6).
    assert "0.600" in html and "0.300" in html
    assert "range" in html

    # Item 7: the best-overall trial (BBB) named, paired per page with reference.
    assert "BBB" in html
    assert "best-overall" in html.lower()

    # Self-contained: every gallery image is a base64 data URI; no sibling PNGs.
    # 3 plots + item6 (4 terms x 3 imgs = 12) + item7 (2 pages x 2 imgs = 4) = 19.
    assert html.count("data:image/png;base64,") == 19
    assert not list(out.glob("*.png"))


def test_report_without_renders_omits_galleries(synthetic_job, tmp_path):
    """A job that predates EP-01 (no renders) still produces a valid report.

    ``jobs/opus47-004`` has no ``verifier/renders/``; the galleries are simply
    skipped rather than erroring, and the items 1-5 report is unaffected.
    """
    report = _load_report_module()
    out = tmp_path / "report_out"

    report.build_report(synthetic_job, out)

    html = (out / "report.html").read_text()
    # Only the three plot images; no gallery sections added.
    assert html.count("data:image/png;base64,") == 3
    assert ">6." not in html
    assert ">7." not in html
