"""Animation perturbation ladder — the deterministic validity proof for the
animation reward (the analogue of Task 1's perturbation study).

We take the *reference* page and derive controlled, increasingly-wrong animation
variants by injecting one ``!important`` override stylesheet (the static design is
untouched — every variant still *settles* to the same look, so the ``static_design``
third stays high and only the animation terms move):

* ``oracle``  — the reference itself (perfect): reward ~1.0, motion ~1.0.
* ``slow``    — every animation 8s long: in the 0-2000ms window the entrance only
                partially plays, so motion is PRESENT but mistimed/under-travelled.
* ``static``  — all animation/transition durations ~0: the page looks settled but
                never moves — a "copied the layout, ignored the motion" candidate.
* ``delayed`` — every animation delayed 4s: the motion happens *after* the capture
                window, so essentially nothing moves in-frame (motion ~0).

The rungs are ordered by *motion correctness* (perfect → partial → none → none).
The proof: reward falls monotonically along that order, the ``oracle`` is the
ceiling, partial motion (``slow``) beats no motion, and — because every variant
still settles to the same design — ``static_design`` stays ~1.0 throughout, so the
reward drop is isolated to the animation terms. Runs ``--no-judge``: no API, fully
deterministic.
"""

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

from .grade_anim import grade

# Each variant is the reference HTML with this rule block injected as a final,
# !important <style> (later + !important ⇒ it wins). Keyed by variant name.
_OVERRIDES = {
    "oracle": "",
    "slow": "*,*::before,*::after{animation-duration:8s!important;}",
    "delayed": "*,*::before,*::after{animation-delay:4s!important;}",
    "static": (
        "*,*::before,*::after{animation-duration:0.001s!important;"
        "animation-delay:0s!important;transition-duration:0s!important;}"
    ),
}

LADDER = ("oracle", "slow", "static", "delayed")


def make_variant(html: str, kind: str) -> str:
    """Return ``html`` with the named override stylesheet injected before </body>."""
    rules = _OVERRIDES[kind]
    if not rules:
        return html
    style = f'<style id="perturb-{kind}">{rules}</style>'
    idx = html.lower().rfind("</body>")
    if idx == -1:
        return html + style
    return html[:idx] + style + html[idx:]


def run_ladder(reference_site_dir, out_dir) -> dict:
    """Grade every ladder variant (deterministic mode) and return the results.

    Writes a ``ladder.json`` summary into ``out_dir`` and returns it.
    """
    reference_site_dir = Path(reference_site_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = (reference_site_dir / "index.html").read_text()
    page_map = {"index": {"expected_file": "index.html"}}

    results = {}
    for kind in LADDER:
        with tempfile.TemporaryDirectory() as tmp:
            cand = Path(tmp)
            (cand / "index.html").write_text(make_variant(html, kind))
            payload = grade(
                cand, reference_site_dir, page_map, cand / "out",
                static_judge=None, anim_judge=None, save_renders=False,
            )
            page = payload["pages"]["index"]
            results[kind] = {
                "reward": payload["reward"],
                "static_design": page["static_design"],
                "motion": page["motion"],
            }

    rewards = [results[k]["reward"] for k in LADDER]
    designs = [results[k]["static_design"] for k in LADDER]
    summary = {
        "ladder": LADDER,
        "results": results,
        # Reward falls monotonically along the motion-correctness order.
        "monotonic_non_increasing": all(
            rewards[i] >= rewards[i + 1] - 1e-9 for i in range(len(rewards) - 1)
        ),
        # The perfect replica is the ceiling.
        "oracle_is_ceiling": rewards[0] >= max(rewards[1:]) - 1e-9,
        # A candidate that animates partially beats one that doesn't animate.
        "partial_motion_beats_none": results["slow"]["reward"] > max(
            results["static"]["reward"], results["delayed"]["reward"]
        ),
        # The drop is isolated to the animation terms: the static design is intact
        # across every variant (they all settle to the same look).
        "static_design_preserved": (max(designs) - min(designs)) < 0.02,
        # Broken animation costs a large, unmistakable share of the reward.
        "broken_margin": rewards[0] - min(rewards[1:]),
    }
    (out_dir / "ladder.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.perturb_anim",
        description="Run the animation perturbation ladder (deterministic validity proof).",
    )
    parser.add_argument("--reference-site", required=True)
    parser.add_argument("--out", default="task2/out/ladder")
    args = parser.parse_args(argv)

    summary = run_ladder(args.reference_site, args.out)
    print(f"{'variant':<10} {'reward':>8} {'static_design':>14} {'motion':>8}")
    for kind in LADDER:
        r = summary["results"][kind]
        print(f"{kind:<10} {r['reward']:>8.4f} {r['static_design']:>14.4f} {r['motion']:>8.4f}")
    print(f"\nmonotonic non-increasing : {summary['monotonic_non_increasing']}")
    print(f"oracle is ceiling        : {summary['oracle_is_ceiling']}")
    print(f"partial motion beats none: {summary['partial_motion_beats_none']}")
    print(f"static design preserved  : {summary['static_design_preserved']}")
    print(f"broken-animation margin  : {summary['broken_margin']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
