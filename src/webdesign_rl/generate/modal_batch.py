"""Batch the per-site gated pipeline over the stratified seed list on Modal.

The per-site pipeline (:func:`generate_gated_site` + emit) is embarrassingly
parallel across seeds and must run **inside the sealed image** that also renders
and grades, so reference screenshots are produced in the exact environment they
are graded in. This module is split — the same pattern as
:class:`AnthropicGenerationClient` — into:

- a **pure, unit-tested core** (no Modal, no network): a deterministic
  :func:`seed_id`; a per-seed worker :func:`run_one_seed` that runs the gated
  pipeline, writes artifacts under ``<out_root>/<seed_id>/``, emits the survivor
  as a Harbor task, and returns a structured :class:`SeedResult`; and
  :func:`summarize_batch`, which reduces a list of ``SeedResult`` to a
  :class:`BatchReport` (gate yield + per-check drop/nudge telemetry); and

- a **thin Modal wrapper** at the bottom of the file (``modal`` imported lazily
  *inside* the functions so this module is import-safe with no Modal installed):
  the ``App`` / sealed ``image`` (the render image) / ``Volume`` / ``Secret``, a
  concurrency-capped ``.map()`` fan-out, and a local entrypoint. The wrapper is
  a shell over the tested core; the live cloud run is a human-in-the-loop step.

**Idempotency.** Each seed owns ``<out_root>/<seed_id>/``; :func:`run_one_seed`
clears and rewrites *only that one* directory, so a re-run of one seed never
touches another seed's artifacts — a mid-batch failure or a targeted re-run is
addressable per seed id.
"""

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .llm_site_generator import Dropped, generate_gated_site
from .seeds import expand_seed

logger = logging.getLogger(__name__)

# The stratified batch size — overgenerate ~48 seeds, gate, keep the survivors.
DEFAULT_BATCH_SIZE = 48

# Concurrency cap on the Modal fan-out: the ~48-seed batch shares one Anthropic
# key, so cap in-flight containers to stay under the rate limit (the client
# already retries/backs off transient 429/529). Tunable without a redeploy.
DEFAULT_CONCURRENCY = 8


@dataclass(frozen=True)
class SeedResult:
    """The structured outcome of running one seed through the gated pipeline.

    ``status`` is ``"passed"`` (a gated survivor emitted as a Harbor task) or
    ``"dropped"`` (declined by the gate). ``check`` names the fatal gate check on
    a drop (``None`` on a pass); ``task_dir`` is the emitted task on a pass
    (``None`` on a drop or when ``emit=False``); ``nudges_by_check`` is the
    per-check nudge tally :func:`summarize_batch` aggregates.
    """

    seed_id: str
    status: str
    check: str | None = None
    reason: str | None = None
    task_dir: Path | None = None
    nudges_by_check: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BatchReport:
    """Aggregate yield + per-check telemetry over a batch of :class:`SeedResult`.

    ``yield_fraction`` is the operationalized "stable recipe" number (survivors /
    total). ``drops_by_check`` and ``nudges_by_check`` are the evidence to tune
    the gate (e.g. whether to relax a specific check) by data rather than guess.
    """

    total: int
    passed: int
    dropped: int
    yield_fraction: float
    drops_by_check: dict
    nudges_by_check: dict


def seed_id(seed, index: int) -> str:
    """A deterministic, filesystem-safe id for ``seed`` at batch position ``index``.

    Shaped ``"{index:03d}_{archetype}_{aesthetic}_{complexity}"`` — the index
    prefix makes ids sort in batch order and guarantees uniqueness across a
    :func:`~webdesign_rl.generate.seeds.sample_seeds` batch even if two seeds
    share the same stratified cell. Stable: same ``(seed, index)`` -> same id.
    """
    parts = [f"{index:03d}", seed.archetype, seed.aesthetic, seed.complexity]
    return "_".join(_slug(p) for p in parts)


def _slug(value: str) -> str:
    """Coerce a token to a filesystem-safe slug (keep ``[A-Za-z0-9_-]``)."""
    safe = [c if (c.isalnum() or c in "-_") else "-" for c in str(value)]
    return "".join(safe)


def run_one_seed(seed, *, index: int, client, render, out_root,
                 emit: bool = True, max_nudges=None) -> SeedResult:
    """Run the full gated pipeline for one seed and return its :class:`SeedResult`.

    Computes the seed's id, writes everything under ``<out_root>/<seed_id>/``
    (the gated ``site/`` and, on a pass, the emitted Harbor ``task/``), and emits
    the survivor via :func:`~webdesign_rl.emit.task_builder.build_task`. On a drop
    it returns the fatal ``check`` + ``reason``; on a pass it returns the
    ``task_dir`` and the per-check nudge tally.

    Idempotent: the seed's own directory is cleared and rewritten, so a re-run
    rebuilds *this* seed without disturbing any other seed under ``out_root``.

    Args:
        seed: a :class:`~webdesign_rl.generate.seeds.Seed` tuple.
        index: the seed's position in the batch (feeds the id + ordering).
        client: a ``GenerationClient`` (stub in tests, Anthropic on Modal).
        render: the render callable threaded into BOTH the gate and emit. On
            Modal this MUST be the direct ``render_site`` (Playwright in-image),
            never ``render_in_container`` (which would nest Docker in the sealed
            container).
        out_root: the volume root every seed's directory lives under.
        emit: package the survivor as a Harbor task (default true).
        max_nudges: optional override of the per-page nudge budget.
    """
    # Lazy: keep this module importable without the emit/render deps wired, and
    # avoid an import cycle (task_builder reaches back into render).
    from ..emit.task_builder import build_task

    sid = seed_id(seed, index)
    seed_dir = Path(out_root) / sid

    # Idempotent re-run: clear ONLY this seed's directory, leaving every other
    # seed's artifacts untouched.
    if seed_dir.exists():
        shutil.rmtree(seed_dir)
    seed_dir.mkdir(parents=True)

    stats: dict = {}
    gate_kwargs = {"render": render, "stats": stats}
    if max_nudges is not None:
        gate_kwargs["max_nudges"] = max_nudges

    result = generate_gated_site(
        expand_seed(seed), client, seed_dir / "site", **gate_kwargs
    )

    nudges = dict(stats.get("nudges_by_check", {}))

    if isinstance(result, Dropped):
        logger.info("seed %s dropped on check=%s: %s",
                    sid, result.check, result.reason)
        return SeedResult(
            seed_id=sid, status="dropped",
            check=result.check, reason=result.reason,
            nudges_by_check=nudges,
        )

    site_dir = result
    page_map = json.loads((site_dir / "page_map.json").read_text())

    task_dir = None
    if emit:
        task_dir = build_task(
            site_dir, page_map, seed_dir / "task", render=render
        )
        logger.info("seed %s passed; emitted task at %s", sid, task_dir)
    else:
        logger.info("seed %s passed (emit skipped)", sid)

    return SeedResult(
        seed_id=sid, status="passed",
        task_dir=task_dir, nudges_by_check=nudges,
    )


def summarize_batch(results) -> BatchReport:
    """Reduce a list of :class:`SeedResult` to a :class:`BatchReport`.

    Pure over its input: computes the gate yield (passed / total; ``0.0`` for an
    empty batch) and the per-check telemetry — ``drops_by_check`` (drop-cause
    counts keyed by the fatal check) and ``nudges_by_check`` (nudge counts summed
    across every result, keyed by check).
    """
    results = list(results)
    total = len(results)
    passed = sum(1 for r in results if r.status == "passed")
    dropped = total - passed

    drops_by_check: dict = {}
    nudges_by_check: dict = {}
    for r in results:
        if r.status == "dropped" and r.check is not None:
            drops_by_check[r.check] = drops_by_check.get(r.check, 0) + 1
        for check, count in (r.nudges_by_check or {}).items():
            nudges_by_check[check] = nudges_by_check.get(check, 0) + count

    yield_fraction = passed / total if total else 0.0
    return BatchReport(
        total=total, passed=passed, dropped=dropped,
        yield_fraction=yield_fraction,
        drops_by_check=drops_by_check, nudges_by_check=nudges_by_check,
    )


def format_report(report: BatchReport) -> str:
    """A compact human/log-friendly rendering of a :class:`BatchReport`."""
    lines = [
        f"batch: {report.passed}/{report.total} passed "
        f"(yield {report.yield_fraction:.1%}); {report.dropped} dropped",
        f"  drops by check: {_fmt_counts(report.drops_by_check)}",
        f"  nudges by check: {_fmt_counts(report.nudges_by_check)}",
    ]
    return "\n".join(lines)


def _fmt_counts(counts: dict) -> str:
    if not counts:
        return "(none)"
    return ", ".join(
        f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    )


# ---------------------------------------------------------------------------
# Thin Modal wrapper — NOT unit-tested. ``modal`` is imported lazily *inside*
# these functions so this whole module stays import-safe with no Modal
# installed (the pure core above is what the tests exercise). The live cloud run
# is the human-in-the-loop step a person drives with ``modal run``.
# ---------------------------------------------------------------------------

# Modal object names (Volume/Secret/App are addressed by name across runs).
APP_NAME = "webdesign-rl-batch"
VOLUME_NAME = "webdesign-rl-artifacts"
SECRET_NAME = "anthropic-api-key"          # holds ANTHROPIC_API_KEY
VOLUME_MOUNT = "/artifacts"                # out_root inside the container


def _build_modal_app():
    """Construct (lazily) the Modal ``App`` + sealed image + volume + worker.

    Returns ``(app, worker)``. ``modal`` is imported here, not at module top,
    so importing :mod:`modal_batch` never requires Modal.

    The sealed image is the **render image** (the verifier's Python + package +
    Chromium + OS-level font palette, built from the SAME font-install block as
    ``render/container``), so the batch renders/grades in the exact image used at
    grade time. Artifacts go to a named ``Volume`` mounted at ``VOLUME_MOUNT``;
    ``ANTHROPIC_API_KEY`` arrives via a named ``Secret``.
    """
    import tempfile

    import modal

    from ..emit.task_builder import _copy_package
    from ..render.container import _RENDER_DOCKERFILE

    app = modal.App(APP_NAME)

    # Reuse the render image VERBATIM: build from the same Dockerfile string and
    # the same baked package the render/container module uses, so the image the
    # batch renders/grades in is byte-for-byte the grade-time image (same Python
    # + package + Chromium + OS-level font palette). No second recipe to drift.
    ctx = Path(tempfile.mkdtemp(prefix="webdesign-rl-modal-"))
    _copy_package(ctx / "webdesign_rl_pkg")
    (ctx / "Dockerfile").write_text(_RENDER_DOCKERFILE)
    image = modal.Image.from_dockerfile(
        str(ctx / "Dockerfile"), context_dir=str(ctx)
    )

    volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
    secret = modal.Secret.from_name(SECRET_NAME)

    # Concurrency cap so the ~48-seed fan-out doesn't trip Anthropic rate limits
    # on the single key (the client already retries/backs off).
    @app.function(
        image=image,
        volumes={VOLUME_MOUNT: volume},
        secrets=[secret],
        max_containers=DEFAULT_CONCURRENCY,
        timeout=60 * 30,
    )
    def _worker(indexed_seed):
        # CRITICAL: we are ALREADY inside the sealed render image, so render
        # with the DIRECT in-image Playwright renderer for BOTH the gate and
        # emit — NOT render_in_container, which would nest Docker in the
        # container. This is the whole point of running the batch in-image.
        from ..render.browser import render_site
        from .client import AnthropicGenerationClient

        index, seed = indexed_seed
        result = run_one_seed(
            seed, index=index,
            client=AnthropicGenerationClient(),
            render=render_site,
            out_root=VOLUME_MOUNT,
        )
        volume.commit()
        return result

    return app, _worker


def run_batch(count: int = DEFAULT_BATCH_SIZE):
    """Local entrypoint: fan ``count`` seeds out on Modal, then report.

    Builds the stratified seed list, ``.map()``s the concurrency-capped worker
    over it (each running the full gated pipeline in the sealed image and writing
    survivors to the volume keyed by seed id), collects the ``SeedResult``s, and
    logs the yield + per-check telemetry. The live invocation is the HITL step:
    ``python -m webdesign_rl.generate.modal_batch`` (with Modal installed +
    authed, the named ``Secret``/``Volume`` provisioned).

    ``app.run()`` is used so the whole entrypoint stays inside the lazily-built
    ``app`` — no module-level ``@app.local_entrypoint`` (which would need ``app``
    at import time and break the import-safety contract).
    """
    from .seeds import sample_seeds

    app, worker = _build_modal_app()
    seeds = sample_seeds(count)

    with app.run():
        results = list(worker.map(list(enumerate(seeds))))

    report = summarize_batch(results)
    logger.info("\n%s", format_report(report))
    print(format_report(report))
    return report


if __name__ == "__main__":  # pragma: no cover - the HITL live-cloud entrypoint.
    logging.basicConfig(level=logging.INFO)
    run_batch()
