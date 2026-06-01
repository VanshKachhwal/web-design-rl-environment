"""Core of the grader validation study: score variants and quantify the claims.

The study proves "higher reward = better replication" by manufacturing variants
whose quality ordering is known (see :mod:`webdesign_rl.grade.perturb`) and
checking the grader's reward respects that ordering. This module holds the
network-free, plot-free computation so it is unit-testable; the report plots and
file I/O live in ``scripts/validate_grader.py``.

Two scoring entry points, both routing through the grader's shared
:func:`~webdesign_rl.grade.grader.score_page` so a variant scores identically
whether it came from an image filter or a re-render:

- :func:`score_image_variant` — score an already-degraded **image** directly
  (image-space perturbations, degenerates). No render.
- :func:`score_site_variant` — **render** an edited HTML site, then score each
  page and aggregate (source-space perturbations, the multi-page check).

Plus the statistics the report quotes: :func:`rank_correlation` (Spearman) and
:func:`pairwise_accuracy` (fraction of severity-ordered pairs the reward ranks
correctly).
"""

from PIL import Image
from scipy.stats import spearmanr

from .aggregate import DIMENSIONS, aggregate
from .grader import score_page


def score_image_variant(candidate_img, reference_img, judge_client) -> dict:
    """Score one candidate image against the reference, as a flat reward payload.

    Routes through the grader's per-image core and the same aggregation the
    single-page grader uses, so an image-space variant is scored by *exactly* the
    grader's logic — minus the HTML render step it doesn't need. Returns
    ``{**dims, "reward": float}``.
    """
    scored = score_page(candidate_img, reference_img, judge_client)
    dims = {dim: scored[dim] for dim in DIMENSIONS}
    return aggregate({"page": dims})


def score_site_variant(site_dir, reference_images, page_map, judge_client) -> dict:
    """Render an edited site and score every page against its reference image.

    ``reference_images`` maps each page name to its reference :class:`PIL.Image`.
    A page whose candidate HTML is missing scores 0 across every dimension (it
    renders to nothing), exactly as the grader treats a missing required page —
    which is what makes "degrade one page lowers the site reward" testable.
    Returns the flat aggregate reward payload across all pages.
    """
    # Imported here so importing the study core doesn't pull in Playwright.
    from ..render.browser import render_site

    rendered = render_site(site_dir, page_map)
    page_scores = {}
    for page in page_map:
        candidate_img = rendered.get(page)
        if candidate_img is None:
            page_scores[page] = None
            continue
        scored = score_page(candidate_img, reference_images[page], judge_client)
        page_scores[page] = {dim: scored[dim] for dim in DIMENSIONS}
    return aggregate(page_scores)


def rank_correlation(severities, values) -> float:
    """Spearman rank correlation between severity and a metric/reward series.

    Higher severity should mean a *lower* score, so a sound metric yields a
    strong **negative** correlation (≈ -1). Returns 0.0 if the series is constant
    (undefined correlation), so a flat axis reads as "no monotonic response"
    rather than NaN.
    """
    rho = spearmanr(severities, values).statistic
    return 0.0 if rho != rho else float(rho)  # NaN guard (constant input)


def pairwise_accuracy(severities, values) -> float:
    """Fraction of severity-ordered pairs whose reward is correctly ranked.

    For every pair where one variant is strictly more severe than the other, the
    less-severe one *should* score at least as high. This reports the fraction of
    such pairs that hold — a direct, interpretable "ordering accuracy" to sit
    beside the rank correlation. Returns 1.0 when there are no ordered pairs.
    """
    correct = total = 0
    n = len(severities)
    for i in range(n):
        for j in range(n):
            if severities[i] < severities[j]:
                total += 1
                # Less severe (i) should score >= more severe (j).
                if values[i] >= values[j]:
                    correct += 1
    return correct / total if total else 1.0
