"""Batch the two-pass animated pipeline over stratified seeds on Modal.

Mirrors Task 1's ``generate/modal_batch.py`` exactly in shape — a **pure, tested
core** (``seed_id`` / ``run_one_anim_seed`` / ``summarize_batch``) plus a **thin
Modal wrapper** (``modal`` imported lazily so the module is import-safe with no
Modal) — adapted for Task 2:

- the worker runs :func:`generate_gated_anim_site` (two passes + lean render gate)
  and emits survivors as 5-page Harbor animation tasks via :func:`emit_anim.build_anim_task`;
- the sealed image is Task 1's **render image** (Playwright + Chromium + fonts +
  the Task-1 package) **plus this Task-2 package** on PYTHONPATH, so generation,
  the gate's filmstrip render, and emit all run in the exact grade-time image;
- separate Modal object names (``webdesign-rl-anim-batch`` / ``-anim-artifacts``) so
  it never collides with the Task-1 batch.

Everything is configurable: ``count`` (overgenerate size), ``concurrency``
(``max_containers``), and the artifact ``volume`` name.
"""

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .seeds_anim import sample_anim_seeds, steer
from .site_generator_anim import Dropped, generate_gated_anim_site

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 24          # the chosen default profile: overgenerate ~24
DEFAULT_CONCURRENCY = 10         # in-flight container cap (shared Anthropic key)
WORKER_CPU = 2.0
WORKER_MEMORY_MB = 4096


@dataclass(frozen=True)
class SeedResult:
    """Structured outcome of one seed: passed / dropped / errored (isolated)."""

    seed_id: str
    status: str
    check: str | None = None
    reason: str | None = None
    task_dir: Path | None = None


@dataclass(frozen=True)
class BatchReport:
    total: int
    passed: int
    dropped: int
    errored: int
    yield_fraction: float
    drops_by_check: dict = field(default_factory=dict)
    errors_by_type: dict = field(default_factory=dict)


def _slug(value: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(value))


def seed_id(seed, style: str, index: int) -> str:
    """Deterministic, sortable id: ``{index:03d}_{archetype}_{aesthetic}_{style}``."""
    parts = [f"{index:03d}", seed.archetype, seed.aesthetic, style]
    return "_".join(_slug(p) for p in parts)


def run_one_anim_seed(seed, style, *, index, client, render, out_root,
                      emit: bool = True) -> SeedResult:
    """Run the two-pass gated pipeline for one seed; emit a survivor as a task.

    Writes everything under ``<out_root>/<seed_id>/`` (``site/`` always; ``task/``
    on a pass). Idempotent per seed. Any unexpected exception is isolated into an
    ``errored`` result so one bad seed never aborts the fan-out.
    """
    from .emit_anim import build_anim_task  # lazy: avoid import cost off Modal

    sid = seed_id(seed, style, index)
    seed_dir = Path(out_root) / sid
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    seed_dir.mkdir(parents=True)

    try:
        result = generate_gated_anim_site(
            steer(seed, style), client, seed_dir / "site", render=render
        )
        if isinstance(result, Dropped):
            logger.info("seed %s dropped on check=%s: %s", sid, result.check, result.reason)
            return SeedResult(seed_id=sid, status="dropped",
                              check=result.check, reason=result.reason)

        task_dir = None
        if emit:
            task_dir = build_anim_task(result, seed_dir / "task")
            logger.info("seed %s passed; emitted task at %s", sid, task_dir)
        return SeedResult(seed_id=sid, status="passed", task_dir=task_dir)
    except Exception as exc:  # noqa: BLE001 - isolate ALL failures per seed
        logger.exception("seed %s errored: %s", sid, exc)
        return SeedResult(seed_id=sid, status="errored",
                          check=type(exc).__name__, reason=str(exc))


def summarize_batch(results) -> BatchReport:
    """Reduce ``SeedResult``s to a :class:`BatchReport` (yield + per-check telemetry)."""
    results = list(results)
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    dropped = sum(1 for r in results if r.status == "dropped")
    errored = sum(1 for r in results if r.status == "errored")
    drops, errors = {}, {}
    for r in results:
        if r.status == "dropped" and r.check:
            drops[r.check] = drops.get(r.check, 0) + 1
        if r.status == "errored" and r.check:
            errors[r.check] = errors.get(r.check, 0) + 1
    return BatchReport(
        total=total, passed=passed, dropped=dropped, errored=errored,
        yield_fraction=(passed / total if total else 0.0),
        drops_by_check=drops, errors_by_type=errors,
    )


def format_report(report: BatchReport) -> str:
    def fmt(d):
        return ", ".join(f"{k}={v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])) or "(none)"
    return (
        f"anim batch: {report.passed}/{report.total} passed "
        f"(yield {report.yield_fraction:.1%}); {report.dropped} dropped, "
        f"{report.errored} errored\n"
        f"  drops by check: {fmt(report.drops_by_check)}\n"
        f"  errors by type: {fmt(report.errors_by_type)}"
    )


# ---------------------------------------------------------------------------
# Thin Modal wrapper — NOT unit-tested. ``modal`` imported lazily inside.
# ---------------------------------------------------------------------------

APP_NAME = "webdesign-rl-anim-batch"
VOLUME_NAME = "webdesign-rl-anim-artifacts"
SECRET_NAME = "anthropic-api-key"
VOLUME_MOUNT = "/artifacts"


def _build_modal_app(*, concurrency=DEFAULT_CONCURRENCY, volume_name=VOLUME_NAME):
    """Build (lazily) the Modal App + sealed image + volume + worker for the batch.

    The image is Task 1's render image (Python + package + Chromium + OS-level font
    palette, built from the SAME Dockerfile) PLUS this Task-2 package on PYTHONPATH,
    so generation / the gate's filmstrip render / emit all run in the grade-time image.
    """
    import tempfile

    import modal

    from webdesign_rl.emit.task_builder import _copy_package
    from webdesign_rl.render.container import _RENDER_DOCKERFILE

    app = modal.App(APP_NAME)

    ctx = Path(tempfile.mkdtemp(prefix="webdesign-rl-anim-modal-"))
    _copy_package(ctx / "webdesign_rl_pkg")                              # Task 1 pkg
    t2 = ctx / "webdesign_rl_anim_pkg" / "webdesign_rl_anim"             # Task 2 pkg
    shutil.copytree(Path(__file__).resolve().parent, t2,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Extend the render Dockerfile: add the Task-2 package + PYTHONPATH.
    dockerfile = _RENDER_DOCKERFILE + (
        "\nCOPY webdesign_rl_anim_pkg /opt/webdesign_rl_anim_pkg\n"
        "ENV PYTHONPATH=/opt/webdesign_rl_anim_pkg\n"
    )
    (ctx / "Dockerfile").write_text(dockerfile)
    image = modal.Image.from_dockerfile(str(ctx / "Dockerfile"), context_dir=str(ctx))

    volume = modal.Volume.from_name(volume_name, create_if_missing=True)
    secret = modal.Secret.from_name(SECRET_NAME)

    @app.function(
        image=image, volumes={VOLUME_MOUNT: volume}, secrets=[secret],
        max_containers=concurrency, cpu=WORKER_CPU, memory=WORKER_MEMORY_MB,
        timeout=60 * 30, serialized=True,
    )
    def _worker(item):
        import logging as _logging
        from webdesign_rl_anim.gen_client import ContinuingGenerationClient
        from webdesign_rl_anim.render_anim import render_filmstrip

        _logging.basicConfig(level=_logging.INFO)
        index, seed, style = item
        # Prefill-free continuing client: the generation model rejects assistant
        # prefill, so when a response hits max_tokens we continue via a trailing
        # USER turn instead. A large plan / shared system completes robustly.
        result = run_one_anim_seed(
            seed, style, index=index,
            client=ContinuingGenerationClient(),
            render=render_filmstrip, out_root=VOLUME_MOUNT,
        )
        volume.commit()
        return result

    return app, _worker


def run_batch(count: int = DEFAULT_BATCH_SIZE, *,
              concurrency: int = DEFAULT_CONCURRENCY, volume: str = VOLUME_NAME):
    """Local entrypoint: fan ``count`` seeds out on Modal, then report the yield."""
    app, worker = _build_modal_app(concurrency=concurrency, volume_name=volume)
    items = [(i, seed, style) for i, (seed, style) in enumerate(sample_anim_seeds(count))]

    with app.run():
        results = []
        for item, outcome in zip(items, worker.map(items, return_exceptions=True)):
            if isinstance(outcome, Exception):
                index, seed, style = item
                sid = seed_id(seed, style, index)
                logger.exception("seed %s failed at infra level: %s", sid, outcome)
                results.append(SeedResult(seed_id=sid, status="errored",
                                          check=type(outcome).__name__, reason=str(outcome)))
            else:
                results.append(outcome)

    report = summarize_batch(results)
    print(format_report(report))
    return report


if __name__ == "__main__":  # pragma: no cover - the HITL live-cloud entrypoint.
    import argparse
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser(prog="python -m webdesign_rl_anim.modal_batch_anim")
    ap.add_argument("--count", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--volume", default=VOLUME_NAME)
    a = ap.parse_args()
    run_batch(a.count, concurrency=a.concurrency, volume=a.volume)
