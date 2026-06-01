"""Grade an animated candidate site against an animated reference.

Reward model (the Part-2 decision: animation is ~2/3 of the score)::

    page_reward = mean(static_design, motion, animation_judge)
    static_design = mean(structure, color, content, design_judge)   # on the SETTLED frame
    reward        = mean(page_reward over pages)                    # absent page -> 0

* ``static_design`` reuses Task 1's grader **unchanged** (imported read-only) on
  the at-rest frame, so a task that nails the static design still earns that third.
* ``motion`` is the deterministic spatio-temporal term (``motion.py``).
* ``animation_judge`` is the VLM rubric over the two filmstrip contact sheets
  (``anim_judge.py``).

The two VLM terms are injectable; pass ``static_judge=None, anim_judge=None`` for
fully-deterministic grading (``--no-judge``): ``static_design`` drops to the three
deterministic terms and ``page_reward = mean(static_design, motion)``. That mode
needs no API key / egress and is the primary oracle + validity check.

``reward.json`` carries only the canonical scalar ``{"reward": <float>}`` (one
metric for Harbor / reward-kit); the full term/sub-score breakdown goes to
``reward-details.json``, and (by default) the exact graded frames + contact
sheets are written to ``<out>/renders/`` so reports use the same pixels.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

from .anim_judge import judge_rubric as anim_judge_rubric
from .filmstrip import contact_sheet
from .motion import motion_score
from .render_anim import DEFAULT_TIMESTAMPS_MS, render_filmstrip

# The four animation/static terms a present page is scored on. ``design_judge``
# and ``animation_judge`` drop out in deterministic-only mode.
DETERMINISTIC_STATIC = ("structure", "color", "content")


def grade(
    candidate_dir,
    reference_site_dir,
    page_map,
    out_dir,
    *,
    static_judge=None,
    anim_judge=None,
    timestamps_ms=DEFAULT_TIMESTAMPS_MS,
    save_renders: bool = True,
):
    """Grade ``candidate_dir`` against ``reference_site_dir`` and write reward files.

    Returns the full reward payload (also written to ``reward-details.json``);
    ``reward.json`` is slimmed to ``{"reward": <float>}``.
    """
    # Task 1 grader, imported read-only (never modified). Lazy so this module
    # stays importable even where webdesign_rl isn't installed.
    from webdesign_rl.grade import metrics
    from webdesign_rl.grade.judge import judge_rubric as design_judge_rubric

    candidate_dir = Path(candidate_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    renders = out_dir / "renders"
    if save_renders:
        renders.mkdir(exist_ok=True)

    page_details = {}
    page_rewards = []

    for page, spec in page_map.items():
        html_file = spec["expected_file"]
        present = (candidate_dir / html_file).exists()

        ref = render_filmstrip(
            reference_site_dir, html_file, timestamps_ms, viewport=1280
        )

        if not present:
            # An absent page scores 0 on every term (mirrors Task 1's policy).
            page_details[page] = {"present": False, "reward": 0.0}
            page_rewards.append(0.0)
            continue

        cand = render_filmstrip(
            candidate_dir, html_file, timestamps_ms, viewport=1280
        )

        # --- static design on the settled frame (Task 1 grader, reused) ---
        static = {
            "structure": metrics.structure(cand["settled"], ref["settled"]),
            "color": metrics.color(cand["settled"], ref["settled"]),
            "content": metrics.content(cand["settled"], ref["settled"]),
        }
        if static_judge is not None:
            dj = design_judge_rubric(cand["settled"], ref["settled"], static_judge)
            static["design_judge"] = dj["design_judge"]
        static_design = statistics.fmean(static.values())

        # --- motion (deterministic) ---
        motion = motion_score(ref["frames"], cand["frames"])

        # --- animation judge (VLM, optional) ---
        terms = {"static_design": static_design, "motion": motion}
        anim_detail = {}
        if anim_judge is not None:
            ref_sheet = contact_sheet(ref["frames"], ref["timestamps_ms"])
            cand_sheet = contact_sheet(cand["frames"], cand["timestamps_ms"])
            aj = anim_judge_rubric(ref_sheet, cand_sheet, anim_judge)
            terms["animation_judge"] = aj["animation_judge"]
            anim_detail = {"animation_judge_sub_scores": aj["sub_scores"]}
            if save_renders:
                ref_sheet.save(renders / f"{page}_ref_contact.png")
                cand_sheet.save(renders / f"{page}_cand_contact.png")

        page_reward = statistics.fmean(terms.values())
        page_rewards.append(page_reward)
        page_details[page] = {
            "present": True,
            "reward": page_reward,
            **terms,
            "static_terms": static,
            "n_animations_ref": ref["n_animations"],
            "n_animations_cand": cand["n_animations"],
            **anim_detail,
        }

        if save_renders:
            ref["settled"].save(renders / f"{page}_ref_settled.png")
            cand["settled"].save(renders / f"{page}_cand_settled.png")
            for t, rf, cf in zip(ref["timestamps_ms"], ref["frames"], cand["frames"]):
                rf.save(renders / f"{page}_ref_t{t:05d}.png")
                cf.save(renders / f"{page}_cand_t{t:05d}.png")

    reward = statistics.fmean(page_rewards) if page_rewards else 0.0
    payload = {
        "reward": reward,
        "timestamps_ms": list(timestamps_ms),
        "pages": page_details,
    }
    (out_dir / "reward.json").write_text(json.dumps({"reward": reward}))
    (out_dir / "reward-details.json").write_text(json.dumps(payload, indent=2))
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.grade_anim",
        description="Grade an animated candidate site against an animated reference.",
    )
    parser.add_argument("--candidate", required=True,
                        help="Directory of the candidate's HTML/CSS (rendered here).")
    parser.add_argument("--reference-site", required=True,
                        help="Directory of the reference animated HTML site.")
    parser.add_argument("--page-map", required=True,
                        help="JSON file mapping page -> {expected_file}.")
    parser.add_argument("--out", required=True,
                        help="Directory to write reward.json / reward-details.json.")
    parser.add_argument("--no-judge", action="store_true",
                        help="Deterministic-only: drop design_judge + animation_judge "
                             "(no VLM call, no API key, no egress).")
    parser.add_argument("--no-save-renders", dest="save_renders",
                        action="store_false",
                        help="Do not persist the graded frames / contact sheets.")
    args = parser.parse_args(argv)

    page_map = json.loads(Path(args.page_map).read_text())

    if args.no_judge:
        static_judge = anim_judge = None
    else:
        from webdesign_rl.grade.judge import AnthropicJudgeClient

        from .anim_judge import AnthropicAnimationJudgeClient

        static_judge = AnthropicJudgeClient()
        anim_judge = AnthropicAnimationJudgeClient()

    payload = grade(
        args.candidate,
        args.reference_site,
        page_map,
        args.out,
        static_judge=static_judge,
        anim_judge=anim_judge,
        save_renders=args.save_renders,
    )
    print(json.dumps({"reward": payload["reward"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
