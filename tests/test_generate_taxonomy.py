"""Behavioral tests for the taxonomy — the single source of design vocabulary.

The taxonomy defines the stratified axes (archetype x aesthetic x complexity),
the free modifier pools, the per-archetype page menus, and the canonical
component catalog. Generation, the manifest, the gate, and curation all reference
this one place, so these tests pin the vocabulary's external shape: the coverage
grid enumerates every axis cell, page menus track complexity and stay in [5, 10]
with their core pages always present, and the component catalog is the single
legal vocabulary.
"""

from webdesign_rl.generate import taxonomy


def test_coverage_grid_enumerates_every_archetype_aesthetic_complexity_cell():
    grid = taxonomy.coverage_grid()
    expected = {
        (a, e, c)
        for a in taxonomy.ARCHETYPES
        for e in taxonomy.AESTHETICS
        for c in taxonomy.COMPLEXITIES
    }
    assert set(grid) == expected
    assert len(grid) == len(taxonomy.ARCHETYPES) * len(taxonomy.AESTHETICS) * len(
        taxonomy.COMPLEXITIES
    )


def test_component_catalog_includes_chrome_atoms_and_sections():
    legal = taxonomy.legal_components()
    # The catalog spans chrome, atoms, and sections — a representative sample
    # from each band must be present.
    assert {"header", "footer"} <= legal  # chrome
    assert {"button", "link", "badge", "form-field", "icon"} <= legal  # atoms
    assert {"hero", "feature-grid", "pricing-table", "cta-banner"} <= legal  # sections


def test_component_catalog_is_the_single_legal_vocabulary():
    # A manifest is legal iff it is a subset of the catalog; anything outside is
    # an improvised, unstyleable component.
    legal = taxonomy.legal_components()
    manifest = ["hero", "feature-grid", "pricing-table", "footer"]
    assert set(manifest) <= legal
    assert "carousel" not in legal  # not in the bounded vocabulary


def test_every_archetype_has_a_page_menu_with_at_least_five_core_pages():
    for archetype in taxonomy.ARCHETYPES:
        menu = taxonomy.page_menu(archetype)
        assert len(menu["core"]) >= 5
        # core + optional never exceeds the 10-page ceiling.
        assert len(menu["core"]) + len(menu["optional"]) <= 10


def test_page_menu_reads_true_per_archetype():
    # The page set must look like the archetype, not a generic template.
    restaurant = taxonomy.page_menu("restaurant-hospitality")
    assert "Menu" in restaurant["core"]
    saas = taxonomy.page_menu("saas-landing")
    assert "Pricing" in (saas["core"] + saas["optional"])


def test_pages_for_count_lands_in_five_to_ten_for_every_cell():
    for archetype in taxonomy.ARCHETYPES:
        for complexity in taxonomy.COMPLEXITIES:
            pages = taxonomy.pages_for(archetype, complexity)
            assert 5 <= len(pages) <= 10


def test_pages_for_count_tracks_complexity():
    # More complex sites are broader: low < high page counts.
    for archetype in taxonomy.ARCHETYPES:
        low = taxonomy.pages_for(archetype, "low")
        med = taxonomy.pages_for(archetype, "med")
        high = taxonomy.pages_for(archetype, "high")
        assert len(low) <= len(med) <= len(high)
        assert len(low) < len(high)


def test_pages_for_always_includes_the_core_pages_and_home_first():
    for archetype in taxonomy.ARCHETYPES:
        menu = taxonomy.page_menu(archetype)
        for complexity in taxonomy.COMPLEXITIES:
            pages = taxonomy.pages_for(archetype, complexity)
            # Core pages are always present regardless of complexity.
            assert set(menu["core"]) <= set(pages)
            # Home leads the sitemap so slug derivation maps it to index.
            assert pages[0] == "Home"
            # No duplicates and only legal menu pages appear.
            assert len(pages) == len(set(pages))
            assert set(pages) <= set(menu["core"]) | set(menu["optional"])
