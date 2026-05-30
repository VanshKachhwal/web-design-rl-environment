"""Stratified seed sampler + expander — deterministic, coverage-spanning draws.

Diversity in the generated batch comes from *spanning the coverage grid in
code*, not from the model's variance. This module turns the taxonomy into:

- a deterministic, ordered list of **seed tuples**
  ``(archetype, aesthetic, complexity, audience, brand_mood)``
  (:func:`sample_seeds`) that **spans** the grid — any prefix of length N
  touches many distinct archetypes *and* aesthetics rather than clustering in
  one corner; and
- an **expander** (:func:`expand_seed`) that turns one seed into the promptable
  spec dict stage 1 already consumes, carrying the complexity-derived page set
  and the chosen aesthetic into the prompt context.

Determinism is structural: the ordering is a fixed function of the index (a
coprime diagonal walk over the grid), so the same count always yields the
identical list. No live/unseeded RNG (``random``/``Math.random``) is used —
that would break the reproducibility the audit trail depends on.
"""

from math import gcd
from typing import NamedTuple

from . import taxonomy


class Seed(NamedTuple):
    """One sampled coverage-grid point + its free modifiers, recorded per site.

    The first three fields are the stratified axes (the coverage cell); the last
    two are free modifiers (sampled, not stratified). The whole tuple is recorded
    per site for auditability and curation.
    """

    archetype: str
    aesthetic: str
    complexity: str
    audience: str
    brand_mood: str


def _coprime_stride(length: int) -> int:
    """A stride coprime to ``length`` so stepping by it visits every index once.

    Using a stride near ``length`` that shares no factor with it makes a single
    additive walk a permutation of the whole range — the basis for spreading
    picks across an axis instead of marching through it in order.
    """
    if length <= 2:
        return 1
    stride = length // 2 + 1
    while gcd(stride, length) != 1:
        stride += 1
    return stride


def sample_seeds(count: int):
    """Return ``count`` seed tuples that deterministically span the grid.

    The three stratified axes are advanced by *coprime strides* per pick, so
    consecutive seeds differ in archetype, aesthetic, *and* complexity and a
    prefix of any length is spread across the grid rather than clustered. The
    free modifiers are likewise stepped deterministically. Same ``count`` ->
    identical list.
    """
    archetypes = taxonomy.ARCHETYPES
    aesthetics = taxonomy.AESTHETICS
    complexities = taxonomy.COMPLEXITIES
    audiences = taxonomy.AUDIENCES
    brand_moods = taxonomy.BRAND_MOODS

    arch_stride = _coprime_stride(len(archetypes))
    aes_stride = _coprime_stride(len(aesthetics))

    seeds_out = []
    for i in range(count):
        archetype = archetypes[(i * arch_stride) % len(archetypes)]
        aesthetic = aesthetics[(i * aes_stride) % len(aesthetics)]
        complexity = complexities[i % len(complexities)]
        audience = audiences[i % len(audiences)]
        brand_mood = brand_moods[i % len(brand_moods)]
        seeds_out.append(
            Seed(archetype, aesthetic, complexity, audience, brand_mood)
        )
    return seeds_out


def expand_seed(seed: Seed) -> dict:
    """Expand a seed tuple into the promptable spec dict stage 1 consumes.

    Carries the stratified axes and free modifiers, plus the *derived* prompt
    context: the complexity-coupled page set (``pages``, ``Home`` first), its
    ``page_count`` (in [5, 10]), and the bounded ``component_catalog`` the
    manifest must stay within. This dict is exactly the ``seed`` argument
    :func:`~webdesign_rl.generate.stages.run_stage1` /
    :func:`~webdesign_rl.generate.llm_site_generator.generate_site` take — the
    sampler "slots in front" with no orchestrator change. The original tuple is
    preserved under ``seed_tuple`` so each site can record it for audit/curation.
    """
    pages = taxonomy.pages_for(seed.archetype, seed.complexity)
    return {
        "archetype": seed.archetype,
        "aesthetic": seed.aesthetic,
        "complexity": seed.complexity,
        "audience": seed.audience,
        "brand_mood": seed.brand_mood,
        "pages": pages,
        "page_count": len(pages),
        "component_catalog": list(taxonomy.COMPONENT_CATALOG),
        "seed_tuple": list(seed),
    }
