"""Harvest a saved Harbor job dir into a normalized scores object (EP-03).

This is the **pure, network-free core** behind ``scripts/report.py``. It turns a
saved job directory (``jobs/<name>/``) into a single normalized scores object,
which is the only contract everything downstream (tables, plots, HTML) reads.

Why the per-trial files are the source of truth: the job-level
``result.json`` records its metrics under a *dynamic* eval key
(e.g. ``claude-code__claude-opus-4-7__adhoc``) and only carries the *mean* across
trials — not the per-trial breakdown. So the per-trial ``verifier/reward.json``
(the five flat terms) and ``verifier/reward-details.json`` (per-page terms + the
judge sub-scores) are read directly, and the dynamic key is never parsed.

The normalized object shape::

    {
      "meta": { task_id, seed_tuple, archetype, aesthetic, complexity, model,
                agent, executor, n_trials, total_cost_usd, total_input_tokens,
                total_output_tokens, started_at, finished_at, wall_clock_sec,
                date, commit },
      "terms": ["structure", "color", "content", "design_judge"],
      "trials": [
        { "trial_id": str,
          "reward": float, "structure": float, "color": float,
          "content": float, "design_judge": float,
          "pages": { <page>: { "present": bool, "structure": ..., "color": ...,
                               "content": ..., "design_judge": ...,
                               "sub_scores": { <sub>: float } } } },
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

#: The four equal-weighted grader terms (``reward`` is their page-mean aggregate).
TERMS = ["structure", "color", "content", "design_judge"]


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


def _first_trial_config(job_dir):
    """The ``config`` block of the first trial's ``result.json`` (or ``{}``).

    The per-trial result is where a real job records agent / model / executor /
    task path — the job-level ``result.json`` carries only timing + aggregate
    stats. Reading the first trial makes provenance robust to that split.
    """
    first_trial = next(iter(sorted(job_dir.glob("task__*"))), None)
    if first_trial is None:
        return {}
    try:
        return _read_json(first_trial / "result.json").get("config", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _seed_tuple(config):
    """Resolve the task's ``seed.json`` from ``config.task.path``.

    The trial config records the task dir; the curated/eval task layout keeps
    ``seed.json`` in the sibling ``site/`` dir (``<task>/../site/seed.json``) or
    inside ``<task>/tests/reference_site/seed.json``. Returns the parsed dict, or
    ``{}`` when no seed.json is found (provenance degrades gracefully).
    """
    task_path = (config.get("task") or {}).get("path")
    if not task_path:
        return {}
    task_path = Path(task_path)
    candidates = [
        task_path.parent / "site" / "seed.json",
        task_path / "tests" / "reference_site" / "seed.json",
        task_path / "solution" / "site" / "seed.json",
    ]
    for cand in candidates:
        if cand.exists():
            return _read_json(cand)
    return {}


def _harvest_meta(job_dir, result, n_trials):
    stats = result.get("stats", {})
    config = _first_trial_config(job_dir)
    agent = config.get("agent") or {}
    started = result.get("started_at")
    finished = result.get("finished_at")
    seed = _seed_tuple(config)

    return {
        "task_id": job_dir.name,
        "seed_tuple": seed.get("seed_tuple"),
        "archetype": seed.get("archetype"),
        "aesthetic": seed.get("aesthetic"),
        "complexity": seed.get("complexity"),
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
    }


def _harvest_trial(trial_dir):
    """Normalize one ``task__<id>/`` directory into a trial record."""
    reward = _read_json(trial_dir / "verifier" / "reward.json")
    details = _read_json(trial_dir / "verifier" / "reward-details.json")

    pages = {}
    for page, pdata in details.get("pages", {}).items():
        pages[page] = {
            "present": pdata.get("present", True),
            **{term: pdata[term] for term in TERMS},
            "sub_scores": dict(pdata.get("design_judge_sub_scores", {})),
        }

    return {
        "trial_id": trial_dir.name.removeprefix("task__"),
        "reward": reward["reward"],
        **{term: reward[term] for term in TERMS},
        "pages": pages,
    }


def harvest(job_dir):
    """Turn a saved Harbor job dir into the normalized scores object."""
    job_dir = Path(job_dir)

    result = _read_json(job_dir / "result.json")
    trials = [
        _harvest_trial(tdir)
        for tdir in sorted(job_dir.glob("task__*"))
        if (tdir / "verifier" / "reward.json").exists()
    ]

    return {
        "meta": _harvest_meta(job_dir, result, len(trials)),
        "terms": list(TERMS),
        "trials": trials,
    }


#: Sentinel "page" used in the long-form CSV for a trial's aggregate terms.
ALL_PAGES = "__all__"


def _csv_rows(scores):
    """Long-form rows: one per (trial, page, term).

    The trial-level aggregate terms (the page-mean reward terms) are emitted
    under the ``__all__`` page sentinel; per-page terms under their page name.
    This shape feeds both the score table and the per-page heatmap directly.
    """
    for trial in scores["trials"]:
        tid = trial["trial_id"]
        for term in [*TERMS, "reward"]:
            yield {"trial_id": tid, "page": ALL_PAGES,
                   "term": term, "value": trial[term]}
        for page, pdata in trial["pages"].items():
            for term in TERMS:
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
# Each is a pure function over the normalized scores object. They produce the
# exact series/matrices the (untested) matplotlib shell consumes, so the numbers
# behind every plot are unit-tested without any plotting.


def reward_series(scores):
    """The per-trial aggregate reward (one value per trial), trial order."""
    return [t["reward"] for t in scores["trials"]]


def summary_stats(values):
    """Median / mean / population-std / min / max of a value series.

    Returns zeros for an empty series so a renderer never divides by nothing.
    """
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
    return {term: [t[term] for t in scores["trials"]] for term in TERMS}


def per_term_mean_std(scores):
    """Per-term mean + population std across trials (feeds the mean-bars plot)."""
    dists = per_term_distributions(scores)
    out = {}
    for term, values in dists.items():
        s = summary_stats(values)
        out[term] = {"mean": s["mean"], "std": s["std"]}
    return out


def per_page_term_matrix(scores):
    """Mean-across-trials value for every (page, term) cell.

    Returns ``{"pages": [...], "terms": [...], "values": [[...]]}`` where
    ``values[i][j]`` is the mean of term ``terms[j]`` on page ``pages[i]`` across
    the trials in which that page is present. Pages are ordered by first
    appearance so the heatmap row order is stable.
    """
    pages = []
    for trial in scores["trials"]:
        for page in trial["pages"]:
            if page not in pages:
                pages.append(page)

    values = []
    for page in pages:
        row = []
        for term in TERMS:
            cells = [
                t["pages"][page][term]
                for t in scores["trials"]
                if page in t["pages"]
            ]
            row.append(float(np.mean(cells)) if cells else float("nan"))
        values.append(row)

    return {"pages": pages, "terms": list(TERMS), "values": values}
