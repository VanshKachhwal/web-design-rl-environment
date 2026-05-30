"""Grader orchestrator: wire load -> metric -> aggregate -> write.

``grade()`` is the standalone entry point. For each page in the ``page_map`` it
loads the candidate and reference screenshots, computes the deterministic
``structure`` (SSIM), ``color`` (palette + CIEDE2000) and ``content`` (OCR
word-multiset F1) terms plus the ``design_judge`` term from an injected VLM judge
client, aggregates the per-page scores into the flat reward payload, and writes
``reward.json`` plus a per-page ``reward-details.json`` (which also records the
judge's rubric sub-scores).

This is the image-first slice (issue 01): inputs are pre-rendered PNG
screenshots, so a page's candidate "file" is its candidate screenshot. Live HTML
rendering is a later issue; the ``page_map`` field name (``expected_file``) is
kept aligned with the cross-issue contract and here names the required candidate
screenshot file.

``page_map`` shape::

    {"home": {"screenshot": "home.png", "expected_file": "home.png"}}

- ``screenshot``: the reference screenshot filename (in ``reference_dir``).
- ``expected_file``: the required candidate screenshot filename (in
  ``candidate_dir``). A required page whose candidate file is missing scores 0.
"""

import json
from pathlib import Path

from PIL import Image

from . import metrics
from .aggregate import DIMENSIONS, aggregate
from .judge import judge_rubric


def grade(candidate_dir, reference_dir, page_map, out_dir, judge_client):
    """Grade a candidate render against the reference, writing the reward files.

    Args:
        candidate_dir: directory of the candidate's screenshot files.
        reference_dir: directory of the reference screenshot files.
        page_map: ``{page: {"screenshot": ref_png, "expected_file": cand_png}}``.
        out_dir: directory to write ``reward.json`` and ``reward-details.json``.
        judge_client: an injected :class:`~webdesign_rl.grade.judge.JudgeClient`
            for the ``design_judge`` term. Inject a ``StubJudgeClient`` for
            deterministic/offline grading; an ``AnthropicJudgeClient`` for live
            VLM scoring. Required and explicit so no live API call is implicit.

    Returns:
        The flat reward payload (also written to ``reward.json``).
    """
    candidate_dir = Path(candidate_dir)
    reference_dir = Path(reference_dir)
    out_dir = Path(out_dir)

    page_scores = {}
    details = {}
    for page, spec in page_map.items():
        reference_img = Image.open(reference_dir / spec["screenshot"])
        candidate_path = candidate_dir / spec["expected_file"]

        if not candidate_path.exists():
            # A required page whose candidate file is missing scores 0 across
            # every dimension and drags the mean. The zeros are derived from
            # DIMENSIONS so a newly added term can't be forgotten here.
            page_scores[page] = None
            details[page] = {
                "present": False,
                **{dim: 0.0 for dim in DIMENSIONS},
            }
            continue

        candidate_img = Image.open(candidate_path)
        rubric = judge_rubric(candidate_img, reference_img, judge_client)
        dims = {
            "structure": metrics.structure(candidate_img, reference_img),
            "color": metrics.color(candidate_img, reference_img),
            "content": metrics.content(candidate_img, reference_img),
            "design_judge": rubric["design_judge"],
        }
        page_scores[page] = dims
        # Log the judge's per-criterion sub-scores alongside the dims so
        # reward-details.json shows exactly how the design_judge term was formed.
        details[page] = {
            "present": True,
            **dims,
            "design_judge_sub_scores": rubric["sub_scores"],
        }

    reward = aggregate(page_scores)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reward.json").write_text(json.dumps(reward, indent=2))
    (out_dir / "reward-details.json").write_text(
        json.dumps({"reward": reward, "pages": details}, indent=2)
    )
    return reward
