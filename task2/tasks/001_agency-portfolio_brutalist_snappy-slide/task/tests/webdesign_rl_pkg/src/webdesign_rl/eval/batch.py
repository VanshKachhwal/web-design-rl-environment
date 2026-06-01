"""Batch-eval pure core: a curated batch dir -> an ordered per-task eval plan.

This is the AFK, unit-tested core of the batch-eval slice (EP-09). It mirrors the
launcher/curate split — a pure plan here + a thin I/O shell in
``scripts/evaluate_all.py`` (the thread pool + ``harbor`` subprocess via
:func:`run_claude_code.launch`). Nothing here touches the network, Harbor, or
Modal; it operates on the directory STRUCTURE of a curated batch and the
``jobs/`` dir, so it is trivial to drive on a temp tree.

Discovery reuses :func:`webdesign_rl.generate.curate.survivors` to find the
fully-emitted tasks. :func:`build_plan` turns ``(batch_dir, jobs_dir, prefix,
force, limit)`` into an ordered list of :class:`TaskPlan` records — one per
survivor, in seed_id order, each carrying the job name and a skip flag.
"""

from dataclasses import dataclass
from pathlib import Path

from ..generate.curate import survivors


@dataclass(frozen=True)
class TaskPlan:
    """One survivor's eval plan record.

    ``seed_id`` is the survivor dir name; ``task_path`` is the str of
    ``<survivor>/task`` (what the launcher runs); ``job_name`` is the job dir name
    under ``jobs/`` (bare seed_id, or ``prefix + seed_id``); ``skip`` is True when
    a finished ``jobs/<job_name>/result.json`` already exists (and not forced).
    """

    seed_id: str
    task_path: str
    job_name: str
    skip: bool


def build_plan(batch_dir, jobs_dir, *, prefix="", force=False, limit=None):
    """Turn a curated batch into an ordered list of :class:`TaskPlan` records.

    One record per survivor (via :func:`curate.survivors`), in seed_id order
    (already sorted). ``job_name`` = ``prefix + seed_id`` (bare seed_id when
    ``prefix`` is empty). A task is skipped when ``not force`` and a finished
    ``jobs/<job_name>/result.json`` exists — a half-written/crashed job dir
    WITHOUT a ``result.json`` is NOT skipped, so it re-runs. ``limit`` caps the
    number of TO-RUN (non-skipped) tasks, leaving the rest skipped; skipped tasks
    don't consume the limit. The existence check is the only I/O.
    """
    jobs_dir = Path(jobs_dir)
    plans = []
    to_run = 0
    for s in survivors(batch_dir):
        job_name = f"{prefix}{s.seed_id}"
        skip = not force and (jobs_dir / job_name / "result.json").exists()
        if not skip and limit is not None and to_run >= limit:
            skip = True
        if not skip:
            to_run += 1
        plans.append(TaskPlan(
            seed_id=s.seed_id,
            task_path=str(s.path / "task"),
            job_name=job_name,
            skip=skip,
        ))
    return plans
