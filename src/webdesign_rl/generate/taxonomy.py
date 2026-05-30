"""The single source of design vocabulary for the generator.

Everything that decides *what kinds of sites exist* lives here — the stratified
axes, the free modifier pools, the per-archetype page menus, and the canonical
component catalog. Generation (stage 1's prompt), the component manifest, the
quality gate, and curation all reference this one module, so the vocabulary can
never diverge between the thing that produces a site and the thing that checks
it (PRD user story #42).

Three things are exposed:

- **The stratified axes** — :data:`ARCHETYPES` (~10), :data:`AESTHETICS` (~10),
  :data:`COMPLEXITIES` (3: low/med/high) — and :func:`coverage_grid`, which
  enumerates their full cartesian product (the cells the seed sampler must span).
- **Per-archetype page menus** — :func:`page_menu` (core >=5 + optional, total
  <=10) and :func:`pages_for`, which couples the page count to the complexity
  axis (design decision #2: low -> 5-6 ... high -> up to 10) so a "complex" site
  is genuinely broader.
- **The canonical component catalog** — :data:`COMPONENT_CATALOG` (the ~20 legal
  component types) and :func:`legal_components`, the single bounded vocabulary a
  site's manifest may draw from.
"""

# --- Stratified axes (design decision #1) ----------------------------------
#
# These three axes form the coverage grid the seed sampler stratifies over.
# Diversity comes from spanning this grid in code, not from model variance.

ARCHETYPES = (
    "saas-landing",
    "agency-portfolio",
    "ecommerce-store",
    "restaurant-hospitality",
    "editorial-blog",
    "nonprofit-civic",
    "personal-resume",
    "event-conference",
    "local-service",
    "docs-product",
)

AESTHETICS = (
    "swiss-editorial",
    "brutalist",
    "neo-brutalist",
    "glassmorphism",
    "corporate-flat",
    "dark-techy",
    "warm-organic",
    "retro-y2k",
    "luxury-serif",
    "playful-rounded",
)

COMPLEXITIES = ("low", "med", "high")


# --- Canonical component catalog (design decision #4) ----------------------
#
# The bounded, ~20-type vocabulary a site's manifest may draw from. Stage 1's
# manifest selects a subset; stage 2 authors exactly that subset, styled for the
# aesthetic; the gate's manifest-compliance check rejects anything outside it.
# Split into three bands purely for readability — :func:`legal_components`
# flattens them into the one legal set.

CHROME_COMPONENTS = ("header", "footer")

ATOM_COMPONENTS = ("button", "link", "badge", "form-field", "icon")

SECTION_COMPONENTS = (
    "hero",
    "feature-grid",
    "content-section",
    "card",
    "pricing-table",
    "testimonial",
    "stat",
    "cta-banner",
    "gallery",
    "logo-cloud",
    "faq",
    "team-card",
    "contact-block",
    "blog-post-card",
    "product-card",
)

# The flat catalog tuple — the union of all three bands, in band order.
COMPONENT_CATALOG = CHROME_COMPONENTS + ATOM_COMPONENTS + SECTION_COMPONENTS


def legal_components():
    """Return the single legal component vocabulary as a frozenset.

    A site's component manifest is well-formed iff it is a *subset* of this set;
    anything outside it is an improvised component stage 2 cannot style and the
    gate must reject.
    """
    return frozenset(COMPONENT_CATALOG)


# --- Free modifiers (sampled, not stratified; design decision #1) ----------
#
# These vary a site's flavor without driving the coverage grid — the sampler
# draws from them but does not stratify over them.

AUDIENCES = (
    "north-american-consumers",
    "european-enterprises",
    "global-developers",
    "local-community",
    "students-and-educators",
    "small-business-owners",
    "creative-professionals",
    "health-and-wellness-seekers",
)

BRAND_MOODS = (
    "confident-and-bold",
    "calm-and-trustworthy",
    "playful-and-energetic",
    "premium-and-understated",
    "warm-and-welcoming",
    "technical-and-precise",
    "rebellious-and-edgy",
    "nostalgic-and-charming",
)


# --- Per-archetype page menus (design decisions #2, #9) --------------------
#
# Each archetype exposes a *core* set (>=5, always present, ``Home`` first so
# slug derivation maps it to ``index``) and an *optional* pool, total <=10. The
# page titles read true for the archetype (a restaurant has a Menu; a SaaS site
# has Pricing) so the sampled sitemap looks human-made, not templated.

_PAGE_MENUS = {
    "saas-landing": {
        "core": ["Home", "Features", "Pricing", "About", "Contact"],
        "optional": ["Integrations", "Customers", "Blog", "Changelog", "Careers"],
    },
    "agency-portfolio": {
        "core": ["Home", "Work", "Services", "About", "Contact"],
        "optional": ["Case Studies", "Process", "Team", "Journal", "Careers"],
    },
    "ecommerce-store": {
        "core": ["Home", "Shop", "Product", "Cart", "Contact"],
        "optional": ["Collections", "About", "Reviews", "Shipping", "FAQ"],
    },
    "restaurant-hospitality": {
        "core": ["Home", "Menu", "About", "Reservations", "Contact"],
        "optional": ["Gallery", "Events", "Private Dining", "Story", "Hours"],
    },
    "editorial-blog": {
        "core": ["Home", "Articles", "Topics", "About", "Contact"],
        "optional": ["Featured", "Authors", "Archive", "Newsletter", "Submit"],
    },
    "nonprofit-civic": {
        "core": ["Home", "Mission", "Programs", "Donate", "Contact"],
        "optional": ["Impact", "Volunteer", "Events", "News", "Partners"],
    },
    "personal-resume": {
        "core": ["Home", "About", "Experience", "Projects", "Contact"],
        "optional": ["Skills", "Writing", "Speaking", "Resume", "Now"],
    },
    "event-conference": {
        "core": ["Home", "Schedule", "Speakers", "Tickets", "Contact"],
        "optional": ["Venue", "Sponsors", "Workshops", "Travel", "FAQ"],
    },
    "local-service": {
        "core": ["Home", "Services", "Pricing", "About", "Contact"],
        "optional": ["Areas", "Gallery", "Reviews", "Booking", "FAQ"],
    },
    "docs-product": {
        "core": ["Home", "Guides", "Reference", "Examples", "Support"],
        "optional": ["Quickstart", "Concepts", "API", "Changelog", "Community"],
    },
}

# Target sitemap length per complexity band (design decision #2): low is
# narrow (5-6), high is broad (up to the 10-page ceiling). Coupling the count to
# this axis is what keeps "complex" coherent — denser *and* broader.
_PAGES_BY_COMPLEXITY = {"low": 5, "med": 7, "high": 10}


def page_menu(archetype):
    """Return ``{"core": [...], "optional": [...]}`` for an archetype.

    ``core`` (>=5, ``Home`` first) is always emitted; ``optional`` is the pool
    the complexity axis draws extra pages from. Returns copies so callers can't
    mutate the shared vocabulary.
    """
    menu = _PAGE_MENUS[archetype]
    return {"core": list(menu["core"]), "optional": list(menu["optional"])}


def target_page_count(complexity):
    """Map a complexity band to its target sitemap length (in [5, 10])."""
    return _PAGES_BY_COMPLEXITY[complexity]


def pages_for(archetype, complexity):
    """Ordered page titles for a site, coupling page count to complexity.

    Always includes every core page (``Home`` first); fills up to the
    complexity-derived target from the optional pool, capped at the 10-page
    ceiling. Deterministic: same ``(archetype, complexity)`` -> same list.
    """
    menu = page_menu(archetype)
    pages = list(menu["core"])
    target = min(target_page_count(complexity), len(menu["core"]) + len(menu["optional"]))
    for optional_page in menu["optional"]:
        if len(pages) >= target:
            break
        pages.append(optional_page)
    return pages


def coverage_grid():
    """Enumerate every ``(archetype, aesthetic, complexity)`` cell.

    Returns the full cartesian product of the three stratified axes in a stable
    order (archetype outermost, complexity innermost). This is the grid the seed
    sampler stratifies over so a batch *spans* the space instead of clustering.
    """
    return [
        (archetype, aesthetic, complexity)
        for archetype in ARCHETYPES
        for aesthetic in AESTHETICS
        for complexity in COMPLEXITIES
    ]
