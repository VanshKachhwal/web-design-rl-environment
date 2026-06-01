"""Unit tests for the Task-2 (animation) eval report harvest + plot-data core.

Task-2 mirror of Task 1's ``tests/test_eval_aggregate.py``. The harvest turns a
saved Harbor job dir into a normalized scores object; the per-trial
``verifier/reward.json`` + ``reward-details.json`` are the source of truth. A
tiny *synthetic* job dir is built under ``tmp_path`` so the tests are fast and
independent of any real job.

The animation grader's per-page record differs from Task 1's: terms are
``static_design / motion / animation_judge`` (the four static terms are nested
under ``static_terms``), an absent page carries only ``{present, reward}``, and
``animation_judge`` is omitted in a ``--no-judge`` deterministic grade.

Run: ``PYTHONPATH=task2 .venv/bin/python -m pytest task2/tests/test_report_anim.py -q``
"""

import csv
import json

import pytest

from webdesign_rl_anim import aggregate_results_anim as agg
from webdesign_rl_anim import report_anim


# --- synthetic fixture job dir ------------------------------------------------


def _apage(static_design, motion, animation_judge=None, static_terms=None,
           n_ref=40, n_cand=42):
    """A present-page record matching the grader's reward-details shape.

    ``page_reward`` is the mean of the scored terms (the grader's composition),
    so a trial's reward equals the page-mean of these.
    """
    terms = {"static_design": static_design, "motion": motion}
    if animation_judge is not None:
        terms["animation_judge"] = animation_judge
    rec = {
        "present": True,
        "reward": sum(terms.values()) / len(terms),
        **terms,
        "static_terms": static_terms or {
            "structure": 0.8, "color": 0.97, "content": 0.6, "design_judge": 0.7,
        },
        "n_animations_ref": n_ref,
        "n_animations_cand": n_cand,
    }
    if animation_judge is not None:
        rec["animation_judge_sub_scores"] = {
            "motion_presence": 0.6, "timing": 0.5, "easing_feel": 0.5,
            "motion_type": 0.6,
        }
    return rec


def _absent_page():
    return {"present": False, "reward": 0.0}


def _write_trial(job_dir, trial_id, pages, task_path, timestamps=(0, 200, 500)):
    """Write one ``task__<id>/`` with the verifier reward files + a trial result."""
    trial_reward = (sum(p["reward"] for p in pages.values()) / len(pages)
                    if pages else 0.0)
    tdir = job_dir / f"task__{trial_id}"
    (tdir / "verifier").mkdir(parents=True)
    (tdir / "verifier" / "reward.json").write_text(json.dumps({"reward": trial_reward}))
    (tdir / "verifier" / "reward-details.json").write_text(json.dumps({
        "reward": trial_reward,
        "timestamps_ms": list(timestamps),
        "pages": pages,
    }))
    (tdir / "result.json").write_text(json.dumps({"config": {
        "task": {"path": task_path},
        "agent": {"name": "claude-code", "model_name": "claude-opus-4-7"},
        "environment": {"type": "modal"},
    }}))
    return trial_reward


def _seed_dir(tmp_path):
    """A curated/eval task layout with seed.json under tests/reference_site/."""
    evaldir = tmp_path / "eval000"
    ref_site = evaldir / "task" / "tests" / "reference_site"
    ref_site.mkdir(parents=True)
    (ref_site / "seed.json").write_text(json.dumps({
        "archetype": "saas-landing",
        "aesthetic": "swiss-editorial",
        "complexity": "low",
        "animation_style": "smooth-fade",
        "seed_tuple": ["saas-landing", "swiss-editorial", "low", "aud", "mood",
                       "smooth-fade"],
    }))
    return str(evaldir / "task")


@pytest.fixture
def synthetic_job(tmp_path):
    """A 2-trial, 2-page animation job (full-judge) with a sibling seed.json."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    task_path = _seed_dir(tmp_path)

    (job_dir / "result.json").write_text(json.dumps({
        "started_at": "2026-06-01T16:00:00.000000",
        "finished_at": "2026-06-01T16:30:00.000000",
        "n_total_trials": 2,
        "stats": {"n_input_tokens": 1000, "n_output_tokens": 200, "cost_usd": 20.0},
    }))

    _write_trial(job_dir, "AAA", {
        "index": _apage(0.8, 0.2, 0.5),
        "about": _apage(0.7, 0.4, 0.55),
    }, task_path)
    _write_trial(job_dir, "BBB", {
        "index": _apage(0.9, 0.3, 0.6),
        "about": _apage(0.8, 0.5, 0.7),
    }, task_path)
    return job_dir


# --- harvest: terms, trial aggregation, reward identity -----------------------


def test_harvest_terms_are_the_three_animation_terms(synthetic_job):
    scores = agg.harvest(synthetic_job)
    assert scores["terms"] == ["static_design", "motion", "animation_judge"]


def test_harvest_trial_term_is_page_mean_and_reward_is_term_mean(synthetic_job):
    """Trial term = mean over pages; reward (from reward.json) = mean of terms."""
    scores = agg.harvest(synthetic_job)
    aaa = next(t for t in scores["trials"] if t["trial_id"] == "AAA")

    # static_design = mean(0.8, 0.7); motion = mean(0.2, 0.4); judge = mean(0.5,0.55)
    assert aaa["static_design"] == pytest.approx(0.75)
    assert aaa["motion"] == pytest.approx(0.30)
    assert aaa["animation_judge"] == pytest.approx(0.525)
    # reward (page-mean of page_rewards 0.5 and 0.55) equals the mean of the terms.
    assert aaa["reward"] == pytest.approx(0.525)
    assert aaa["reward"] == pytest.approx(
        (aaa["static_design"] + aaa["motion"] + aaa["animation_judge"]) / 3
    )


def test_harvest_keeps_per_page_static_terms_and_anim_subscores(synthetic_job):
    scores = agg.harvest(synthetic_job)
    page = next(t for t in scores["trials"] if t["trial_id"] == "AAA")["pages"]["index"]

    assert page["present"] is True
    assert page["static_terms"]["color"] == pytest.approx(0.97)
    assert page["anim_sub_scores"]["timing"] == pytest.approx(0.5)
    assert page["n_animations_ref"] == 40 and page["n_animations_cand"] == 42


def test_harvest_timestamps_from_first_trial(synthetic_job):
    scores = agg.harvest(synthetic_job)
    assert scores["timestamps_ms"] == [0, 200, 500]
    assert scores["meta"]["timestamps_ms"] == [0, 200, 500]


def test_harvest_run_metadata_and_seed_provenance(synthetic_job):
    meta = agg.harvest(synthetic_job)["meta"]
    assert meta["model"] == "claude-opus-4-7"
    assert meta["agent"] == "claude-code"
    assert meta["executor"] == "modal"
    assert meta["n_trials"] == 2
    assert meta["total_cost_usd"] == pytest.approx(20.0)
    assert meta["wall_clock_sec"] == pytest.approx(1800.0)
    # Seed provenance, including the Task-2 animation-style axis.
    assert meta["archetype"] == "saas-landing"
    assert meta["aesthetic"] == "swiss-editorial"
    assert meta["complexity"] == "low"
    assert meta["animation_style"] == "smooth-fade"


# --- adaptive terms + absent pages --------------------------------------------


def test_no_judge_job_drops_animation_judge_term(tmp_path):
    """A deterministic (no-VLM) grade omits ``animation_judge`` on every page."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    task_path = _seed_dir(tmp_path)
    (job_dir / "result.json").write_text(json.dumps(
        {"started_at": None, "finished_at": None, "n_total_trials": 1, "stats": {}}))
    _write_trial(job_dir, "DET", {
        "index": _apage(0.8, 0.2),          # no animation_judge key
        "about": _apage(0.7, 0.4),
    }, task_path)

    scores = agg.harvest(job_dir)
    assert scores["terms"] == ["static_design", "motion"]
    det = scores["trials"][0]
    assert "animation_judge" not in det
    # reward identity still holds across the two surviving terms.
    assert det["reward"] == pytest.approx((det["static_design"] + det["motion"]) / 2)


def test_absent_page_scores_zero_on_every_term(tmp_path):
    """An absent page (present=False) contributes 0 to each trial-level term."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    task_path = _seed_dir(tmp_path)
    (job_dir / "result.json").write_text(json.dumps(
        {"started_at": None, "finished_at": None, "n_total_trials": 1, "stats": {}}))
    _write_trial(job_dir, "MISS", {
        "index": _apage(0.9, 0.6, 0.6),
        "contact": _absent_page(),
    }, task_path)

    scores = agg.harvest(job_dir)
    trial = scores["trials"][0]
    contact = trial["pages"]["contact"]
    assert contact["present"] is False
    assert contact["static_design"] == 0.0 and contact["motion"] == 0.0
    # trial-level motion = mean(0.6 present, 0.0 absent) = 0.3.
    assert trial["motion"] == pytest.approx(0.3)


# --- persistence --------------------------------------------------------------


def test_write_scores_json_roundtrips(synthetic_job, tmp_path):
    scores = agg.harvest(synthetic_job)
    out = tmp_path / "out"
    agg.write_scores(scores, out)
    assert json.loads((out / "scores.json").read_text()) == scores


def test_write_scores_csv_is_long_form(synthetic_job, tmp_path):
    """One row per (trial, page, term); a ``__all__`` page holds trial-level terms."""
    scores = agg.harvest(synthetic_job)
    out = tmp_path / "out"
    agg.write_scores(scores, out)
    with open(out / "scores.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert {"trial_id", "page", "term", "value"} <= set(rows[0])
    agg_motion = [r for r in rows if r["trial_id"] == "AAA"
                  and r["page"] == "__all__" and r["term"] == "motion"]
    assert len(agg_motion) == 1 and float(agg_motion[0]["value"]) == pytest.approx(0.3)
    page_motion = [r for r in rows if r["trial_id"] == "AAA"
                   and r["page"] == "about" and r["term"] == "motion"]
    assert len(page_motion) == 1 and float(page_motion[0]["value"]) == pytest.approx(0.4)


# --- pure plot-data computations ----------------------------------------------


def test_reward_series_and_summary_stats(synthetic_job):
    scores = agg.harvest(synthetic_job)
    series = agg.reward_series(scores)
    # AAA reward 0.525; BBB reward mean(0.6, 0.66667) = 0.63333.
    assert sorted(series) == pytest.approx([0.525, 0.633333], abs=1e-5)
    s = agg.summary_stats(series)
    assert s["min"] == pytest.approx(0.525)
    assert s["max"] == pytest.approx(0.633333, abs=1e-5)


def test_per_term_mean_std(synthetic_job):
    scores = agg.harvest(synthetic_job)
    ms = agg.per_term_mean_std(scores)
    # motion trial values: AAA 0.30, BBB 0.40 -> mean 0.35, std 0.05.
    assert ms["motion"]["mean"] == pytest.approx(0.35)
    assert ms["motion"]["std"] == pytest.approx(0.05)
    # static_design trial values: AAA mean(0.8,0.7)=0.75, BBB mean(0.9,0.8)=0.85.
    assert ms["static_design"]["mean"] == pytest.approx(0.80)


def test_per_page_term_matrix_present_only_mean(synthetic_job):
    scores = agg.harvest(synthetic_job)
    matrix = agg.per_page_term_matrix(scores)
    assert set(matrix["pages"]) == {"index", "about"}
    assert matrix["terms"] == ["static_design", "motion", "animation_judge"]
    # motion on "about": mean of 0.4 (AAA) and 0.5 (BBB) = 0.45.
    cell = matrix["values"][matrix["pages"].index("about")][
        matrix["terms"].index("motion")]
    assert cell == pytest.approx(0.45)


def test_per_page_term_matrix_never_present_page_is_nan(tmp_path):
    """A page absent in every trial is NaN in the heatmap (no render to average)."""
    import math
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    task_path = _seed_dir(tmp_path)
    (job_dir / "result.json").write_text(json.dumps(
        {"started_at": None, "finished_at": None, "n_total_trials": 1, "stats": {}}))
    _write_trial(job_dir, "T", {
        "index": _apage(0.8, 0.3, 0.5),
        "contact": _absent_page(),
    }, task_path)

    matrix = agg.per_page_term_matrix(agg.harvest(job_dir))
    contact_motion = matrix["values"][matrix["pages"].index("contact")][
        matrix["terms"].index("motion")]
    assert math.isnan(contact_motion)


def _write_static_trial(job_dir, trial_id):
    """A Task-1-shaped (static) trial: DICT top-level reward, no timestamps_ms."""
    tdir = job_dir / f"task__{trial_id}"
    (tdir / "verifier").mkdir(parents=True)
    (tdir / "verifier" / "reward.json").write_text(json.dumps({"reward": 0.7}))
    (tdir / "verifier" / "reward-details.json").write_text(json.dumps({
        "reward": {"structure": 0.7, "color": 0.9, "content": 0.5,
                   "design_judge": 0.6},
        "pages": {"index": {"present": True, "structure": 0.7, "color": 0.9,
                            "content": 0.5, "design_judge": 0.6,
                            "design_judge_sub_scores": {}}},
    }))
    (tdir / "result.json").write_text(json.dumps({"config": {}}))


def test_is_anim_job_distinguishes_static_and_animation(synthetic_job, tmp_path):
    """The animation grade is detected by timestamps_ms + a numeric reward."""
    assert agg.is_anim_job(synthetic_job) is True

    static = tmp_path / "static_job"
    static.mkdir()
    (static / "result.json").write_text(json.dumps({"stats": {}}))
    _write_static_trial(static, "S1")
    assert agg.is_anim_job(static) is False


def test_build_report_refuses_static_job(tmp_path):
    """A static (Task-1) job is refused, not turned into an all-zero-terms report."""
    static = tmp_path / "static_job"
    static.mkdir()
    (static / "result.json").write_text(json.dumps({"stats": {}}))
    _write_static_trial(static, "S1")
    with pytest.raises(ValueError):
        report_anim.build_report(static, tmp_path / "out")


def test_discover_jobs_direct_children_only(tmp_path):
    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    for name in ("job-b", "job-a"):
        (jobs_dir / name).mkdir()
        (jobs_dir / name / "result.json").write_text("{}")
    trial = jobs_dir / "job-a" / "task__abc"
    trial.mkdir()
    (trial / "result.json").write_text("{}")  # deeper — must NOT be a job
    (jobs_dir / "not-a-job").mkdir()

    found = agg.discover_jobs(jobs_dir)
    assert found == [jobs_dir / "job-a", jobs_dir / "job-b"]


# --- report shell: self-contained html + markdown (items 1-5, no galleries) ---


def test_build_report_writes_self_contained_html(synthetic_job, tmp_path):
    out = tmp_path / "report_out"
    report_anim.build_report(synthetic_job, out)

    assert (out / "scores.json").exists() and (out / "scores.csv").exists()
    html = (out / "report.html").read_text()

    # Three plots (items 3,4,5) embedded as base64; no sibling PNGs; no galleries.
    assert html.count("data:image/png;base64,") == 3
    assert not list(out.glob("*.png"))
    assert ">6." not in html and ">7." not in html
    # Items 1-5 headings present.
    for n in range(1, 6):
        assert f">{n}." in html
    # Provenance text: animation style + model; score-table trial ids + terms.
    assert "smooth-fade" in html
    assert "claude-opus-4-7" in html
    assert "AAA" in html and "BBB" in html
    assert "static_design" in html and "motion" in html and "animation_judge" in html


def test_build_report_markdown_writes_report_md_and_plot_pngs(synthetic_job, tmp_path):
    out = tmp_path / "report_out_md"
    report_anim.build_report(synthetic_job, out, fmt="markdown")

    md = (out / "report.md").read_text()
    assert md.startswith("# Animation model-eval report")
    assert "## 5. Per-page × per-term heatmap" in md
    # The three plots are sibling PNG files (GitHub-native), not base64.
    for png in ("distributions.png", "per_term_means.png", "heatmap.png"):
        assert (out / png).exists()
    assert (out / "scores.json").exists()
