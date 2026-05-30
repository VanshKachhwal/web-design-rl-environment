"""Pure aggregation of per-page, per-dimension scores into the reward payload.

The aggregation is deliberately dimension-agnostic so the later terms (``color``,
``content``, ``design_judge``) slot in without touching this module: it discovers
the dimensions present and averages each one across pages.

Contract:

- A page score is the mean of its dimension terms.
- The task ``reward`` is the mean of the per-page scores across all pages.
- A required page whose candidate is missing contributes 0 across every
  dimension, dragging the mean. Such pages are passed as ``None``.

``reward.json`` is the flat payload returned here (``reward`` plus each dimension
key). The richer per-page breakdown for ``reward-details.json`` is built by the
grader, which owns I/O.
"""

# Dimensions scored in this issue. Adding a later term means appending here and
# producing it per page; the aggregation math is unchanged.
DIMENSIONS = ("structure", "color", "content", "design_judge")


def aggregate(
    page_scores: dict[str, dict[str, float] | None],
    dimensions: tuple[str, ...] = DIMENSIONS,
) -> dict[str, float]:
    """Combine ``{page: {dimension: score} | None}`` into the flat reward payload.

    A page mapped to ``None`` represents a required page whose candidate is
    missing; every dimension scores 0 for it. The returned payload has one float
    per dimension plus the scalar ``reward``, each in [0, 1].

    ``dimensions`` selects which terms form the reward; it defaults to the full
    four-term blend. The deterministic-only grading mode passes the three
    deterministic dims (dropping ``design_judge``) so the reward is the mean of
    just those terms — the math is otherwise identical.
    """
    pages = list(page_scores.values())

    # Per-dimension mean across pages (missing page => 0 for that dimension).
    dims: dict[str, float] = {}
    for dim in dimensions:
        per_page = [0.0 if p is None else p.get(dim, 0.0) for p in pages]
        dims[dim] = sum(per_page) / len(per_page) if per_page else 0.0

    # Per-page score = mean of its dimensions (missing page => 0).
    page_means = []
    for p in pages:
        if p is None:
            page_means.append(0.0)
        else:
            terms = [p.get(dim, 0.0) for dim in dimensions]
            page_means.append(sum(terms) / len(terms) if terms else 0.0)
    reward = sum(page_means) / len(page_means) if page_means else 0.0

    return {**dims, "reward": reward}
