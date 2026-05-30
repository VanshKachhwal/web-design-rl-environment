"""Behavioral tests for the stratified seed sampler + seed expander.

The sampler draws a deterministic, ordered list of seed tuples that *spans* the
coverage grid (no single-cell clustering), so a batch covers many distinct
archetypes and aesthetics rather than collapsing. The expander turns one seed
into the promptable spec object stage 1 already consumes (carrying the
complexity-derived page set and the chosen aesthetic into the prompt context).
These tests pin that external behavior; the sampler is pure (no live RNG that
breaks reproducibility), so the tests are deterministic.
"""

from webdesign_rl.generate import seeds, taxonomy


def test_sampling_is_deterministic_for_same_count():
    # Same count -> byte-identical ordered list (no unseeded RNG).
    first = seeds.sample_seeds(48)
    second = seeds.sample_seeds(48)
    assert first == second


def test_sampling_yields_the_requested_count():
    assert len(seeds.sample_seeds(48)) == 48
    assert len(seeds.sample_seeds(10)) == 10


def test_sampling_spans_archetypes_and_aesthetics_no_clustering():
    batch = seeds.sample_seeds(48)
    archetypes = {s.archetype for s in batch}
    aesthetics = {s.aesthetic for s in batch}
    complexities = {s.complexity for s in batch}
    # A batch of ~48 touches every archetype and every aesthetic, and all three
    # complexity bands — it spans the grid rather than clustering in one corner.
    assert archetypes == set(taxonomy.ARCHETYPES)
    assert aesthetics == set(taxonomy.AESTHETICS)
    assert complexities == set(taxonomy.COMPLEXITIES)


def test_sampling_does_not_cluster_in_a_single_cell():
    batch = seeds.sample_seeds(48)
    cells = [(s.archetype, s.aesthetic, s.complexity) for s in batch]
    # No single coverage cell dominates the batch.
    most_common = max(cells.count(cell) for cell in set(cells))
    assert most_common <= 2


def test_small_batch_still_spreads_archetypes():
    # Even a 10-site batch must not repeat a single archetype throughout.
    batch = seeds.sample_seeds(10)
    archetypes = {s.archetype for s in batch}
    assert len(archetypes) >= 8


def test_expand_seed_carries_the_axes_and_modifiers_into_prompt_context():
    seed = seeds.Seed(
        archetype="restaurant-hospitality",
        aesthetic="warm-organic",
        complexity="low",
        audience="local-community",
        brand_mood="warm-and-welcoming",
    )
    spec = seeds.expand_seed(seed)
    # Every axis + modifier is threaded into the promptable context.
    assert spec["archetype"] == "restaurant-hospitality"
    assert spec["aesthetic"] == "warm-organic"
    assert spec["complexity"] == "low"
    assert spec["audience"] == "local-community"
    assert spec["brand_mood"] == "warm-and-welcoming"


def test_expand_seed_carries_complexity_derived_pages_and_count():
    seed = seeds.Seed(
        "restaurant-hospitality", "warm-organic", "low",
        "local-community", "warm-and-welcoming",
    )
    spec = seeds.expand_seed(seed)
    expected_pages = taxonomy.pages_for("restaurant-hospitality", "low")
    # The complexity-coupled page set is carried verbatim (Home first, count in
    # [5, 10]) so stage 1 designs the sitemap the seed implies.
    assert spec["pages"] == expected_pages
    assert spec["page_count"] == len(expected_pages)
    assert 5 <= spec["page_count"] <= 10
    assert spec["pages"][0] == "Home"


def test_expand_seed_carries_the_legal_component_catalog():
    seed = seeds.sample_seeds(1)[0]
    spec = seeds.expand_seed(seed)
    # The bounded vocabulary travels with the spec so stage 1's manifest stays
    # a subset of the catalog.
    assert set(spec["component_catalog"]) == set(taxonomy.legal_components())


def test_expand_seed_output_is_accepted_by_run_stage1():
    # The expander's output is a dict stage 1 consumes directly (it is the seed
    # ``generate_site``/``run_stage1`` take). Round-trip it through the stubbed
    # stage-1 runner to prove the shape is accepted end-to-end.
    import json

    from webdesign_rl.generate import stages
    from webdesign_rl.generate.client import StubGenerationClient

    seed = seeds.sample_seeds(1)[0]
    spec_input = seeds.expand_seed(seed)

    canned = {
        "brief": "x",
        "pages": [{"title": t, "sections": ["hero"]} for t in spec_input["pages"]],
        "component_manifest": ["hero"],
    }
    client = StubGenerationClient(responses=[json.dumps(canned)])
    result = stages.run_stage1(spec_input, client)
    assert result.pages[0]["slug"] == "index"
    assert len(result.pages) == spec_input["page_count"]
