"""Orchestrate the two-pass animated generation into a gated site directory.

Per-site flow (the lean Task-2 analogue of Task 1's ``generate_gated_site``):

    Pass 1 (plan + shared system)  -> write styles.css / animations.css
    Pass 2 (build all page bodies) -> assemble + write each <slug>.html
    lean render gate               -> pass: keep; fail: one full rebuild retry, else drop

No per-page structured nudge loop (we dropped the manifest structure that made it
clean); instead a single whole-site rebuild retry, then drop. Over-generation
absorbs the looser bar. Every drop is logged with its machine reason.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .gate_anim_lean import run_lean_gate
from .render_anim import render_filmstrip
from .two_pass import (
    ANIMATIONS_CSS,
    STYLES_CSS,
    Plan,
    PlanError,
    assemble_page,
    run_build,
    run_plan,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_REBUILDS = 1  # whole-site Pass-2 rebuilds before dropping


@dataclass(frozen=True)
class Dropped:
    """A site the orchestrator declined to keep, with the machine reason + check."""

    reason: str
    check: str | None = None


def _gate_render(site_dir, html_file):
    """Filmstrip render used by the gate (kept small/fast for gating)."""
    return render_filmstrip(site_dir, html_file)


def generate_gated_anim_site(steer, client, out_dir, *, render=_gate_render,
                             max_rebuilds=DEFAULT_MAX_REBUILDS):
    """Generate one gated animated site, or return :class:`Dropped`.

    Args:
        steer: the soft creative-steer dict (``seeds_anim.steer``).
        client: a generation ``GenerationClient`` (stub in tests, Anthropic in prod).
        out_dir: directory to write the site into.
        render: filmstrip render callable for the gate (injectable for tests).
        max_rebuilds: whole-site Pass-2 rebuild retries before dropping.

    Returns the site ``Path`` on a pass, else :class:`Dropped`.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Pass 1: plan + shared system ---
    try:
        plan = run_plan(steer, client)
    except PlanError as exc:
        return _drop(steer, f"plan pass failed: {exc}", check="plan")
    (out_dir / STYLES_CSS).write_text(plan.styles_css)
    (out_dir / ANIMATIONS_CSS).write_text(plan.animations_css)
    (out_dir / "page_map.json").write_text(json.dumps(plan.page_map, indent=2))
    (out_dir / "seed.json").write_text(json.dumps(steer, indent=2))

    # --- Pass 2 (+ rebuild retry) + lean gate ---
    for attempt in range(max_rebuilds + 1):
        bodies = run_build(plan, client)
        _write_pages(out_dir, plan, bodies)
        diags = run_lean_gate(out_dir, plan, render)
        if not diags:
            logger.info("site passed lean gate (%d pages)", len(plan.pages))
            return out_dir
        checks = sorted({d["check"] for d in diags})
        logger.info("gate failed (attempt %d/%d): %s",
                    attempt + 1, max_rebuilds + 1, checks)
        if attempt == max_rebuilds:
            d = diags[0]
            return _drop(steer, f"lean gate failed after {max_rebuilds} rebuild(s): "
                                f"{d['page']}: {d['message']}", check=d["check"])
    return _drop(steer, "unreachable", check="internal")  # pragma: no cover


def _write_pages(out_dir: Path, plan: Plan, bodies: dict) -> None:
    for page in plan.pages:
        body = bodies.get(page["slug"], "")
        html = assemble_page(page["title"], body, plan)
        (out_dir / f"{page['slug']}.html").write_text(html)


def _drop(steer, reason, *, check=None) -> Dropped:
    logger.warning("dropping site for steer %s: %s",
                   steer.get("seed_tuple", steer), reason)
    return Dropped(reason=reason, check=check)
