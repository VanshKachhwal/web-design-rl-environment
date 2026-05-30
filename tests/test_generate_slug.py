"""Behavioral tests for deterministic slug / ``page_map`` derivation.

The sitemap is the single source of truth for page identity. Each page title
derives one stable *slug*, and that one token derives the three downstream
identities: the expected agent file (``<slug>.html``), the reference screenshot
(``<slug>.png``), and the ``page_map`` key. These tests pin that derivation —
home->index, slugify, collision suffixes, reserved-stem avoidance, and the
one-token->three-derivations consistency the emit/grader consume.
"""

from webdesign_rl.generate.slug import derive_page_map, slugify


def test_home_title_becomes_index():
    assert slugify("Home", is_home=True) == "index"


def test_only_home_may_take_index():
    # A non-home page titled "Home" must not steal the reserved ``index`` stem.
    assert slugify("Home", is_home=False) != "index"


def test_slugify_lowercases_and_hyphenates():
    assert slugify("About Us") == "about-us"


def test_slugify_ascii_folds_accents():
    assert slugify("Café Menu") == "cafe-menu"


def test_slugify_truncates_to_40_chars():
    title = "A" * 100
    slug = slugify(title)
    assert len(slug) <= 40


def test_slugify_strips_punctuation_and_collapses_separators():
    assert slugify("Pricing & Plans!!!") == "pricing-plans"


def test_derive_page_map_keys_each_slug_to_three_consistent_derivations():
    page_map = derive_page_map(["Home", "About Us", "Contact"])
    assert set(page_map) == {"index", "about-us", "contact"}
    for slug, spec in page_map.items():
        assert spec == {
            "screenshot": f"{slug}.png",
            "expected_file": f"{slug}.html",
        }


def test_derive_page_map_resolves_collisions_with_numeric_suffix():
    page_map = derive_page_map(["Home", "Services", "Services"])
    assert "services" in page_map
    assert "services-2" in page_map
    assert len(page_map) == 3


def test_derive_page_map_avoids_reserved_stems():
    # A page literally titled "Variables" must not collide with variables.css.
    page_map = derive_page_map(["Home", "Variables", "Components", "Fonts"])
    assert "variables" not in page_map
    assert "components" not in page_map
    assert "fonts" not in page_map
    assert len(page_map) == 4


def test_first_page_is_home_index():
    page_map = derive_page_map(["Landing", "About"])
    # The first sitemap entry is the home page regardless of its title.
    assert "index" in page_map
