"""Behavioral tests for the batch-eval pure plan (EP-09).

``evaluate-all`` runs the existing per-task eval over every survivor in a curated
batch dir, a few in parallel. The thread pool + ``harbor`` subprocess is the
untested shell; the unit-tested seam is the pure *plan*: turning a batch dir +
jobs dir + flags into an ordered list of per-task plan records (which task to run,
under which job name, whether to skip because a finished ``result.json`` exists).

The synthetic batch tree reuses the curate fixture shape: a seed dir named
``{index:03d}_{archetype}_{aesthetic}_{complexity}`` is a *survivor* iff it has a
``task/task.toml`` (a *drop* has only ``site/``). A *completed* job is
``jobs/<job_name>/result.json``; a half-written/crashed job dir has no
``result.json``. No network / Harbor / Modal.
"""

from pathlib import Path

from webdesign_rl.eval import batch as eval_batch


def _seed_dir(batch_dir: Path, name: str, *, survivor: bool) -> Path:
    """One synthetic seed dir; a survivor gets ``task/task.toml``, a drop only
    ``site/`` (mirrors the curate fixture helper)."""
    d = batch_dir / name
    (d / "site").mkdir(parents=True)
    if survivor:
        (d / "task").mkdir()
        (d / "task" / "task.toml").write_text("")
    return d


def _pool(batch_dir: Path, survivors, drops=()):
    """Build a synthetic batch dir from survivor + drop dir-name lists."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    for name in survivors:
        _seed_dir(batch_dir, name, survivor=True)
    for name in drops:
        _seed_dir(batch_dir, name, survivor=False)
    return batch_dir


def _completed_job(jobs_dir: Path, job_name: str) -> Path:
    """A finished job: ``jobs/<job_name>/result.json`` present."""
    d = jobs_dir / job_name
    d.mkdir(parents=True)
    (d / "result.json").write_text("{}")
    return d


def _half_written_job(jobs_dir: Path, job_name: str) -> Path:
    """A crashed/half-written job: the dir exists but has NO ``result.json``."""
    d = jobs_dir / job_name
    d.mkdir(parents=True)
    (d / "trial-0").mkdir()
    return d


def test_plan_discovers_survivors_and_excludes_drops(tmp_path):
    """The plan covers exactly the survivor tasks (drop-only dirs excluded),
    pointing each job at ``<survivor>/task`` in seed_id order."""
    batch = _pool(
        tmp_path / "batch",
        survivors=[
            "001_agency-portfolio_brutalist_med",
            "000_saas-landing_swiss-editorial_low",
        ],
        drops=["002_editorial-blog_corporate-flat_high"],
    )

    plans = eval_batch.build_plan(batch, tmp_path / "jobs")

    assert [p.seed_id for p in plans] == [
        "000_saas-landing_swiss-editorial_low",
        "001_agency-portfolio_brutalist_med",
    ]
    first = plans[0]
    assert first.task_path == str(
        batch / "000_saas-landing_swiss-editorial_low" / "task"
    )
    assert first.job_name == "000_saas-landing_swiss-editorial_low"
    assert all(not p.skip for p in plans)


def test_plan_skips_completed_but_not_half_written_jobs(tmp_path):
    """A job whose result.json exists is skipped; a half-written job dir without
    a result.json is NOT skipped (so a crashed run re-runs)."""
    done = "000_saas-landing_swiss-editorial_low"
    crashed = "001_agency-portfolio_brutalist_med"
    fresh = "002_editorial-blog_corporate-flat_high"
    batch = _pool(tmp_path / "batch", survivors=[done, crashed, fresh])
    jobs = tmp_path / "jobs"
    _completed_job(jobs, done)
    _half_written_job(jobs, crashed)

    by_id = {p.seed_id: p for p in eval_batch.build_plan(batch, jobs)}

    assert by_id[done].skip is True
    assert by_id[crashed].skip is False
    assert by_id[fresh].skip is False


def test_force_runs_everything_including_completed(tmp_path):
    """--force ignores existing result.json and re-runs completed jobs."""
    done = "000_saas-landing_swiss-editorial_low"
    batch = _pool(tmp_path / "batch", survivors=[done])
    jobs = tmp_path / "jobs"
    _completed_job(jobs, done)

    plans = eval_batch.build_plan(batch, jobs, force=True)

    assert plans[0].skip is False


def test_prefix_namespaces_job_name(tmp_path):
    """job_name is the bare seed_id by default; --prefix prepends to namespace
    it (and so the skip-completed check looks under the namespaced job dir)."""
    seed = "000_saas-landing_swiss-editorial_low"
    batch = _pool(tmp_path / "batch", survivors=[seed])
    jobs = tmp_path / "jobs"

    plans = eval_batch.build_plan(batch, jobs, prefix="opus47-")

    assert plans[0].job_name == "opus47-" + seed
    # A completed job under the namespaced name skips it.
    _completed_job(jobs, "opus47-" + seed)
    plans = eval_batch.build_plan(batch, jobs, prefix="opus47-")
    assert plans[0].skip is True


def test_limit_caps_to_run_count_not_skipped(tmp_path):
    """--limit caps the number of TO-RUN (non-skipped) tasks; already-completed
    tasks don't consume the limit, and order stays deterministic (seed_id)."""
    done = "000_saas-landing_swiss-editorial_low"
    a = "001_agency-portfolio_brutalist_med"
    b = "002_editorial-blog_corporate-flat_high"
    c = "003_docs-site_minimal-mono_low"
    batch = _pool(tmp_path / "batch", survivors=[done, a, b, c])
    jobs = tmp_path / "jobs"
    _completed_job(jobs, done)

    plans = eval_batch.build_plan(batch, jobs, limit=2)

    # done is skipped (completed, free); then exactly 2 of a/b/c run, last skipped.
    to_run = [p.seed_id for p in plans if not p.skip]
    assert to_run == [a, b]
    assert [p.seed_id for p in plans if p.skip] == [done, c]
