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

On disk ``reward.json`` carries only the single canonical scalar
``{"reward": <float>}`` so Harbor (and any reward-kit consumer) sees exactly one,
unambiguous metric to optimize. The full four-term breakdown is not lost: it lives
in ``reward-details.json`` (under its top-level ``"reward"`` key) and in
``grade()``'s in-process return value.

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


def score_page(candidate_img, reference_img, judge_client) -> dict:
    """Score one candidate screenshot against one reference screenshot.

    The pure per-image core of grading: it computes the deterministic
    ``structure`` (SSIM), ``color`` (palette + CIEDE2000) and ``content`` (OCR
    F1) terms plus the ``design_judge`` term from the injected judge client, and
    returns the per-page breakdown::

        {"structure": float, "color": float, "content": float,
         "design_judge": float, "design_judge_sub_scores": {field: float, ...}}

    When ``judge_client`` is ``None`` the ``design_judge`` term is omitted
    entirely (no VLM call) — the deterministic-only grading mode, which needs no
    API key or network egress. The deterministic terms are unaffected.

    This is deliberately independent of the file-render/IO path: ``grade()``
    obtains the candidate image by rendering HTML, while the validation study
    feeds it an already-degraded image directly. Both share *this* logic so the
    numbers are identical regardless of where the image came from.
    """
    scored = {
        "structure": metrics.structure(candidate_img, reference_img),
        "color": metrics.color(candidate_img, reference_img),
        "content": metrics.content(candidate_img, reference_img),
    }
    if judge_client is not None:
        rubric = judge_rubric(candidate_img, reference_img, judge_client)
        scored["design_judge"] = rubric["design_judge"]
        scored["design_judge_sub_scores"] = rubric["sub_scores"]
    return scored


def grade(candidate_dir, reference_dir, page_map, out_dir, judge_client,
          save_renders: bool = True):
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
            Pass ``None`` for **deterministic-only** grading: the ``design_judge``
            term is dropped and the reward is the mean of the three deterministic
            terms — no VLM call, API key, or network egress.
        save_renders: persist the exact candidate screenshots that were scored
            into ``out_dir/renders/<page>.png`` (on by default), so reports use
            the same pixels — same sealed render + bundled fonts — that produced
            each score, with no local re-render. A page whose candidate HTML is
            absent is simply skipped (no PNG). Independent of whether the judge
            ran, so deterministic-only grading persists the same renders. Pass
            ``False`` to grade without writing any PNGs.

    Returns:
        The full flat reward payload (each dimension term plus the aggregate
        ``reward``). Only the on-disk ``reward.json`` is slimmed to the single
        scalar ``{"reward": <float>}`` — this return value and
        ``reward-details.json`` retain the complete four-term breakdown.
    """
    candidate_dir = Path(candidate_dir)
    reference_dir = Path(reference_dir)
    out_dir = Path(out_dir)

    # Deterministic-only mode (judge_client=None) drops the design_judge dim, so
    # the missing-page zeros and the aggregation span exactly the scored terms.
    dimensions = (
        DIMENSIONS
        if judge_client is not None
        else tuple(d for d in DIMENSIONS if d != "design_judge")
    )

    # Render every candidate page in one browser session. A page whose HTML file
    # is absent is simply omitted from the result (handled as a missing page
    # below), so a missing required page still scores 0.
    rendered = render_site(candidate_dir, page_map, viewport=_VIEWPORT)

    # Persist the *exact* candidate screenshots being scored as a grading
    # byproduct, keyed by page so a report pairs each with its reference. A page
    # whose HTML was absent isn't in ``rendered``, so it is simply skipped (no
    # PNG). Independent of the judge, so deterministic-only grading saves the
    # same renders.
    if save_renders:
        renders_dir = out_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)
        for page, candidate_img in rendered.items():
            candidate_img.save(renders_dir / f"{page}.png")

    page_scores = {}
    details = {}
    for page, spec in page_map.items():
        reference_img = Image.open(reference_dir / spec["screenshot"])
        candidate_img = rendered.get(page)

        if candidate_img is None:
            # A required page whose candidate HTML is missing scores 0 across
            # every scored dimension and drags the mean. The zeros are derived
            # from the active dimensions so a newly added term can't be forgotten.
            page_scores[page] = None
            details[page] = {
                "present": False,
                **{dim: 0.0 for dim in dimensions},
            }
            continue

        scored = score_page(candidate_img, reference_img, judge_client)
        # The judge sub-scores are present only when a judge ran (omitted in
        # deterministic-only mode); pop so they don't enter the aggregated dims.
        sub_scores = scored.pop("design_judge_sub_scores", None)
        page_scores[page] = scored
        # Log the judge's per-criterion sub-scores alongside the dims so
        # reward-details.json shows exactly how the design_judge term was formed.
        details[page] = {"present": True, **scored}
        if sub_scores is not None:
            details[page]["design_judge_sub_scores"] = sub_scores

    reward = aggregate(page_scores, dimensions)

    out_dir.mkdir(parents=True, exist_ok=True)
    # On disk, reward.json carries only the single canonical scalar so Harbor (and
    # any reward-kit consumer) sees exactly one, unambiguous metric to optimize.
    # The full four-term breakdown lives in reward-details.json (under "reward")
    # and in this function's in-process return value — no information is lost.
    (out_dir / "reward.json").write_text(
        json.dumps({"reward": reward["reward"]}, indent=2)
    )
    (out_dir / "reward-details.json").write_text(
        json.dumps({"reward": reward, "pages": details}, indent=2)
    )
    return reward
