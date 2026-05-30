"""Grader orchestrator: wire render -> metric -> aggregate -> write.

``grade()`` is the standalone entry point. It **renders the candidate** directory
of HTML/CSS itself (headless Chromium over a local HTTP server, offline and
deterministic — see :mod:`webdesign_rl.render.browser`), then for each page in
the ``page_map`` compares the rendered candidate screenshot to the committed
reference screenshot, computes the deterministic ``structure`` (SSIM), ``color``
(palette + CIEDE2000) and ``content`` (OCR word-multiset F1) terms plus the
``design_judge`` term from an injected VLM judge client, aggregates the per-page
scores into the flat reward payload, and writes ``reward.json`` plus a per-page
``reward-details.json`` (which also records the judge's rubric sub-scores).

Since issue 05 the candidate is **source HTML**, not pre-made screenshots: the
grader renders what the agent actually produced. The reference stays a directory
of committed PNG screenshots — "the screenshots shown to the agent" — rendered
once with the same module so the comparison is apples-to-apples.

``page_map`` shape::

    {"home": {"screenshot": "home.png", "expected_file": "index.html"}}

- ``screenshot``: the reference screenshot filename (in ``reference_dir``).
- ``expected_file``: the required candidate **HTML** filename (in
  ``candidate_dir``). A required page whose candidate HTML is missing renders to
  nothing and scores 0 across every dimension.
"""

import json
from pathlib import Path

from PIL import Image

from ..render.browser import render_site
from . import metrics
from .aggregate import DIMENSIONS, aggregate
from .judge import judge_rubric

# Capture width for candidate rendering; matches the viewport the reference PNGs
# were rendered at (design decision: 1280px desktop, full scroll height).
_VIEWPORT = 1280


def grade(candidate_dir, reference_dir, page_map, out_dir, judge_client):
    """Grade a candidate HTML site against the reference, writing the reward files.

    Args:
        candidate_dir: directory of the candidate's HTML/CSS/asset files. The
            grader renders this itself into per-page screenshots.
        reference_dir: directory of the reference screenshot PNGs.
        page_map: ``{page: {"screenshot": ref_png, "expected_file": cand_html}}``.
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

    # Render every candidate page in one browser session. A page whose HTML file
    # is absent is simply omitted from the result (handled as a missing page
    # below), so a missing required page still scores 0.
    rendered = render_site(candidate_dir, page_map, viewport=_VIEWPORT)

    page_scores = {}
    details = {}
    for page, spec in page_map.items():
        reference_img = Image.open(reference_dir / spec["screenshot"])
        candidate_img = rendered.get(page)

        if candidate_img is None:
            # A required page whose candidate HTML is missing scores 0 across
            # every dimension and drags the mean. The zeros are derived from
            # DIMENSIONS so a newly added term can't be forgotten here.
            page_scores[page] = None
            details[page] = {
                "present": False,
                **{dim: 0.0 for dim in DIMENSIONS},
            }
            continue

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
