"""Harvest a saved Task-2 (animation) Harbor job into a normalized scores object.

Task-2 mirror of Task 1's ``webdesign_rl.eval.aggregate_results`` — duplicated
(not imported) so Task 1 stays frozen and this package is self-contained. The
shape of the animation grader's ``reward-details.json`` differs from Task 1's, so
the harvest differs in three ways:

* **Terms are the animation page-reward terms** ``static_design / motion /
  animation_judge`` (Task 1's four static terms live *nested* under each page's
  ``static_terms`` and are preserved for drill-down, but are not the report's
  top-level terms). The term set is **adaptive**: ``animation_judge`` is dropped
  when the job was graded ``--no-judge`` (no VLM), so a deterministic job reports
  two terms.
* **There is no trial-level term aggregate on disk** — the grader writes only the
  per-page terms plus the page-mean ``reward`` scalar. So the trial-level value of
  each term is derived here as the **mean over all pages** (an absent page counts
  as 0 on every term, mirroring the grader's absent-page-→-0 reward policy). That
  identity makes ``reward == mean(static_design, motion, animation_judge)`` hold
  per trial, exactly as the grader composes it.
* **Per-page records carry the animation extras** (``static_terms`` sub-dict, the
  ``animation_judge`` sub-scores, and the declared-animation counts) so a reader
  can drill into a page without re-grading.

The normalized object shape::

    {
      "meta": { task_id, seed_tuple, archetype, aesthetic, complexity,
                animation_style, model, agent, executor, n_trials,
                total_cost_usd, total_input_tokens, total_output_tokens,
                started_at, finished_at, wall_clock_sec, date, commit },
      "terms": ["static_design", "motion", "animation_judge"],   # adaptive
      "timestamps_ms": [...],
      "trials": [
        { "trial_id": str, "reward": float,
          "static_design": float, "motion": float, "animation_judge": float,
          "pages": { <page>: { "present": bool, "reward": float,
                               "static_design": ..., "motion": ...,
                               "animation_judge": ...,
                               "static_terms": { structure, color, content,
                                                 design_judge },
                               "anim_sub_scores": { <sub>: float },
                               "n_animations_ref": int|None,
                               "n_animations_cand": int|None } } },
        ...
      ],
    }
"""

import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np

#: The animation page-reward terms, in display order. ``reward`` is their
#: per-page mean, aggregated over pages. The set is narrowed adaptively per job
#: (``animation_judge`` drops out for a ``--no-judge`` deterministic grade).
CANONICAL_TERMS = ["static_design", "motion", "animation_judge"]

#: Sentinel "page" used in the long-form CSV for a trial's aggregate terms.
ALL_PAGES = "__all__"


def _read_json(path):
    return json.loads(Path(path).read_text())


def _wall_clock_sec(started_at, finished_at):
    """Seconds between two ISO timestamps, or ``None`` if either is missing."""
    if not started_at or not finished_at:
        return None
    delta = datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    return delta.total_seconds()


def _repo_commit():
    """Short repo commit for provenance, or ``None`` outside a git checkout."""
    try:
        out = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _trial_dirs(job_dir):
    """The per-trial dirs under a job, sorted, identified by their reward file.

    A Harbor trial dir is ``<task-name>__<short-id>/`` — and the task name VARIES
    in Task 2 (``aurora__…``, ``000_saas-landing_swiss-editorial__…``, …), unlike
    Task 1's fixed ``task__…``. So a trial dir is detected by the presence of its
    ``verifier/reward.json`` rather than by a name prefix. The job-level
    ``result.json`` lives at the job root (not a child dir), so it is excluded.
    """
    return [
        d for d in sorted(job_dir.iterdir())
        if d.is_dir() and (d / "verifier" / "reward.json").exists()
    ]


def _trial_id(trial_dir):
    """The short trial id: the segment after the last ``__`` (or the full name)."""
    name = trial_dir.name
    return name.rsplit("__", 1)[-1] if "__" in name else name


def _first_trial_config(job_dir):
    """The ``config`` block of the first trial's ``result.json`` (or ``{}``).

    A real job records agent / model / executor / task path on the *per-trial*
    result; the job-level ``result.json`` carries only timing + aggregate stats.
    """
    trials = _trial_dirs(job_dir)
    if not trials:
        return {}
    try:
        return _read_json(trials[0] / "result.json").get("config", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _seed_tuple(config):
    """Resolve the task's ``seed.json`` from ``config.task.path``.

    Task 2's emitted task copies the whole reference site (including its
    ``seed.json``) under ``<task>/tests/reference_site/``; a curated seed dir also
    keeps it in the sibling ``<task>/../site/``. Returns the parsed dict, or
    ``{}`` when none is found (provenance degrades gracefully — e.g. the hand-made
    Aurora demo writes a seed.json with no ``seed_tuple``).
    """
    task_path = (config.get("task") or {}).get("path")
    if not task_path:
        return {}
    task_path = Path(task_path)
    candidates = [
        task_path / "tests" / "reference_site" / "seed.json",
        task_path.parent / "site" / "seed.json",
        task_path / "solution" / "site" / "seed.json",
    ]
    for cand in candidates:
        if cand.exists():
            try:
                return _read_json(cand)
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def _harvest_meta(job_dir, result, n_trials, timestamps_ms):
    stats = result.get("stats", {})
    config = _first_trial_config(job_dir)
    agent = config.get("agent") or {}
    started = result.get("started_at")
    finished = result.get("finished_at")
    seed = _seed_tuple(config)
    tup = seed.get("seed_tuple") or []

    return {
        "task_id": job_dir.name,
        "seed_tuple": seed.get("seed_tuple"),
        "archetype": seed.get("archetype", tup[0] if len(tup) > 0 else None),
        "aesthetic": seed.get("aesthetic", tup[1] if len(tup) > 1 else None),
        "complexity": seed.get("complexity", tup[2] if len(tup) > 2 else None),
        # Task-2-specific: the animation-style steer is the last seed-tuple axis
        # (and is also recorded flat by the scaling pipeline's steer dict).
        "animation_style": seed.get(
            "animation_style", tup[-1] if len(tup) > 3 else None
        ),
        "model": agent.get("model_name"),
        "agent": agent.get("name"),
        "executor": (config.get("environment") or {}).get("type"),
        "n_trials": result.get("n_total_trials", n_trials),
        "total_cost_usd": stats.get("cost_usd"),
        "total_input_tokens": stats.get("n_input_tokens"),
        "total_output_tokens": stats.get("n_output_tokens"),
        "started_at": started,
        "finished_at": finished,
        "wall_clock_sec": _wall_clock_sec(started, finished),
        "date": (finished or "")[:10] or None,
        "commit": _repo_commit(),
        "timestamps_ms": timestamps_ms,
    }


def _trial_raws(job_dir):
    """``(trial_id, reward, details)`` for every gradeable trial dir."""
    for tdir in _trial_dirs(job_dir):
        reward = _read_json(tdir / "verifier" / "reward.json")["reward"]
        details = _read_json(tdir / "verifier" / "reward-details.json")
        yield _trial_id(tdir), reward, details


def _derive_terms(raws):
    """The animation terms actually scored on ≥1 present page, in canonical order.

    ``animation_judge`` is only written when the grade ran with a VLM; a
    ``--no-judge`` deterministic grade therefore reports just
    ``static_design / motion``. Falls back to the full canonical set when no page
    is present anywhere (so a degenerate all-absent job still has columns).
    """
    present_terms = set()
    for _, _, details in raws:
        for pdata in details.get("pages", {}).values():
            if pdata.get("present"):
                present_terms.update(t for t in CANONICAL_TERMS if t in pdata)
    ordered = [t for t in CANONICAL_TERMS if t in present_terms]
    return ordered or list(CANONICAL_TERMS)


def _build_trial(trial_id, reward, details, terms):
    """Normalize one trial: per-page records + trial-level term means.

    ``reward`` is the canonical page-mean scalar from ``reward.json``. Each
    trial-level term is the mean of its per-page values over **all** pages, with
    an absent page contributing 0 (mirroring the grader's absent-page-→-0
    policy), so ``reward == mean(terms)`` holds.
    """
    pages = {}
    term_vals = {term: [] for term in terms}
    for page, pdata in details.get("pages", {}).items():
        present = pdata.get("present", True)
        rec = {
            "present": present,
            "reward": pdata.get("reward", 0.0),
            "static_terms": dict(pdata.get("static_terms", {})) if present else {},
            "anim_sub_scores":
                dict(pdata.get("animation_judge_sub_scores", {})) if present else {},
            "n_animations_ref": pdata.get("n_animations_ref") if present else None,
            "n_animations_cand": pdata.get("n_animations_cand") if present else None,
        }
        for term in terms:
            rec[term] = pdata.get(term, 0.0) if present else 0.0
            term_vals[term].append(rec[term])
        pages[page] = rec

    trial = {"trial_id": trial_id, "reward": reward}
    for term in terms:
        vals = term_vals[term]
        trial[term] = float(np.mean(vals)) if vals else 0.0
    trial["pages"] = pages
    return trial


def harvest(job_dir):
    """Turn a saved Task-2 Harbor job dir into the normalized scores object."""
    job_dir = Path(job_dir)
    result = _read_json(job_dir / "result.json")

    raws = list(_trial_raws(job_dir))
    terms = _derive_terms(raws)
    trials = [_build_trial(tid, reward, details, terms)
              for tid, reward, details in raws]

    # The filmstrip sample points are identical across trials (deterministic);
    # read them from the first trial's details for the provenance header.
    timestamps_ms = raws[0][2].get("timestamps_ms") if raws else None

    return {
        "meta": _harvest_meta(job_dir, result, len(trials), timestamps_ms),
        "terms": terms,
        "timestamps_ms": timestamps_ms,
        "trials": trials,
    }


# --- persistence --------------------------------------------------------------


def _csv_rows(scores):
    """Long-form rows: one per (trial, page, term).

    Trial-level aggregate terms (+ reward) are emitted under the ``__all__`` page
    sentinel; per-page terms under their page name.
    """
    terms = scores["terms"]
    for trial in scores["trials"]:
        tid = trial["trial_id"]
        for term in [*terms, "reward"]:
            yield {"trial_id": tid, "page": ALL_PAGES,
                   "term": term, "value": trial[term]}
        for page, pdata in trial["pages"].items():
            for term in terms:
                yield {"trial_id": tid, "page": page,
                       "term": term, "value": pdata[term]}


def write_scores(scores, out_dir):
    """Persist the normalized object as ``scores.json`` + long-form ``scores.csv``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    with open(out_dir / "scores.csv", "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["trial_id", "page", "term", "value"])
        writer.writeheader()
        for row in _csv_rows(scores):
            writer.writerow(row)


# --- pure plot-data computations ----------------------------------------------
#
# Each is a pure function over the normalized scores object, producing exactly
# the series/matrices the (untested) matplotlib shell consumes — so the numbers
# behind every plot are unit-tested without any plotting.


def reward_series(scores):
    """The per-trial aggregate reward (one value per trial), trial order."""
    return [t["reward"] for t in scores["trials"]]


def summary_stats(values):
    """Median / mean / population-std / min / max of a value series."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {k: 0.0 for k in ("median", "mean", "std", "min", "max")}
    return {
        "median": float(np.median(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),  # population std (ddof=0)
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def per_term_distributions(scores):
    """For each term, the per-trial value series (feeds the per-term box plots)."""
    return {term: [t[term] for t in scores["trials"]] for term in scores["terms"]}


def per_term_mean_std(scores):
    """Per-term mean + population std across trials (feeds the mean-bars plot)."""
    out = {}
    for term, values in per_term_distributions(scores).items():
        s = summary_stats(values)
        out[term] = {"mean": s["mean"], "std": s["std"]}
    return out


def per_page_term_matrix(scores):
    """Mean-across-trials value for every (page, term) cell.

    Returns ``{"pages": [...], "terms": [...], "values": [[...]]}`` where
    ``values[i][j]`` is the mean of ``terms[j]`` on ``pages[i]`` across the trials
    in which that page was **present** (a page absent in a trial carries no real
    render, so it is excluded from that cell's mean — matching Task 1). A page
    absent in every trial is ``NaN``. Pages are ordered by first appearance.
    """
    terms = scores["terms"]
    pages = []
    for trial in scores["trials"]:
        for page in trial["pages"]:
            if page not in pages:
                pages.append(page)

    values = []
    for page in pages:
        row = []
        for term in terms:
            cells = [
                t["pages"][page][term]
                for t in scores["trials"]
                if page in t["pages"] and t["pages"][page].get("present", True)
            ]
            row.append(float(np.mean(cells)) if cells else float("nan"))
        values.append(row)

    return {"pages": pages, "terms": list(terms), "values": values}


# --- pure selection logic for the GIF galleries (report §6/§7) -----------------
#
# These pick the concrete (trial, page) cells the report's animated galleries
# show. Pure over the normalized scores object (no images) so the choice of which
# evidence to surface is unit-tested; building the GIFs from the saved filmstrip
# frames is the untested shell in ``report_anim``.


def _term_cells(scores, term):
    """Every present (trial, page) cell for ``term`` as ``(trial_id, page, score)``."""
    for trial in scores["trials"]:
        for page, pdata in trial["pages"].items():
            if pdata.get("present", True):
                yield trial["trial_id"], page, pdata[term]


def per_metric_extrema(scores):
    """For each term, the best- and worst-scoring (trial, page) cell.

    Returns, per term, ``{"best": {trial_id,page,score}, "worst": {...},
    "range": [min, max]}`` — taken at the trial×page level so the gallery can show
    the exact filmstrip behind each number. A term with no present cell is omitted.
    """
    out = {}
    for term in scores["terms"]:
        cells = list(_term_cells(scores, term))
        if not cells:
            continue
        best = max(cells, key=lambda c: c[2])
        worst = min(cells, key=lambda c: c[2])
        out[term] = {
            "best": {"trial_id": best[0], "page": best[1], "score": best[2]},
            "worst": {"trial_id": worst[0], "page": worst[1], "score": worst[2]},
            "range": [worst[2], best[2]],
        }
    return out


def best_overall_trial(scores):
    """The ``trial_id`` of the highest-``reward`` trial (the ceiling visual)."""
    trials = scores["trials"]
    if not trials:
        return None
    return max(trials, key=lambda t: t["reward"])["trial_id"]


def gallery_available(job_dir):
    """True when ≥1 trial has persisted filmstrip frames (``verifier/renders/``).

    A job graded with ``--no-save-renders`` (or one predating render persistence)
    has no frames to build GIFs from, so the galleries are skipped and the report
    degrades to the five data sections.
    """
    for tdir in _trial_dirs(Path(job_dir)):
        if any((tdir / "verifier" / "renders").glob("*_t*.png")):
            return True
    return False


def discover_jobs(jobs_dir):
    """The job dirs directly under ``jobs_dir`` carrying a ``result.json``, sorted.

    Scans only immediate children (no recursion): each trial subdir has its own
    ``result.json`` one level deeper but is never a direct child of the jobs root,
    so it is naturally excluded. This returns ALL jobs (static + animation); use
    :func:`is_anim_job` to keep only the animation ones in a mixed dir.
    """
    jobs_dir = Path(jobs_dir)
    return sorted(
        d for d in jobs_dir.iterdir()
        if d.is_dir() and (d / "result.json").exists()
    )


def is_anim_job(job_dir):
    """True iff ``job_dir`` was graded by the Task-2 *animation* grader.

    A Task-1 (static) job often sits in the same ``jobs/`` dir; harvesting it with
    this animation harvester would yield a misleading all-zero-terms report
    (its pages carry ``structure/color/...``, never ``static_design/motion/...``).
    The two grades are told apart by their ``reward-details.json``: the animation
    grader always writes a numeric top-level ``reward`` **plus** a ``timestamps_ms``
    list (the filmstrip sample points), whereas Task 1 writes a *dict* ``reward``
    and no ``timestamps_ms``. Detected from the first gradeable trial; ``False``
    for static, empty, or unreadable jobs — so a mixed dir reports only animation
    jobs.
    """
    job_dir = Path(job_dir)
    for tdir in _trial_dirs(job_dir):
        try:
            details = _read_json(tdir / "verifier" / "reward-details.json")
        except (FileNotFoundError, json.JSONDecodeError):
            return False
        return "timestamps_ms" in details and not isinstance(
            details.get("reward"), dict
        )
    return False
