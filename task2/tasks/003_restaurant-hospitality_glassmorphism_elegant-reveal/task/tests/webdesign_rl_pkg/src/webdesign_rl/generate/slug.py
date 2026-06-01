"""Deterministic slug / ``page_map`` derivation — page identity in one token.

The sitemap is the single source of truth for page identity. Each page title is
reduced to one stable **slug**, and that single token derives everything
downstream: the expected agent file (``<slug>.html``), the reference screenshot
(``<slug>.png``), and the ``page_map`` key the emit/grader consume. Deriving all
three from one token (rather than authoring them separately) is what guarantees
the candidate<->reference pairing lines up by construction.

The rules (design decision #9):

- **Home -> ``index``.** Only the home page (the first sitemap entry) may take
  the reserved ``index`` stem.
- **Else ``slugify(title)``** — lowercase, ASCII-fold accents, hyphenate, strip
  punctuation, collapse separators, truncate to <=40 chars.
- **Collisions -> numeric suffix** (``services``, ``services-2``, ...).
- **Reserved stems** (``index``, ``variables``, ``components``, ``fonts``) are
  avoided for non-home pages, since those filenames belong to the design-system
  artifacts and would clobber them.

Pure and deterministic: the same sitemap always yields the same ``page_map``.
"""

import re
import unicodedata

# Stems owned by the design-system artifacts (and the home page). A non-home page
# may never resolve to one of these, or its ``<slug>.html`` would clobber the
# frozen ``variables.css``/``components.css``/``fonts`` or the home ``index.html``.
RESERVED_STEMS = frozenset({"index", "variables", "components", "fonts"})

# The reserved stem the home page (and only the home page) takes.
HOME_SLUG = "index"

_MAX_SLUG_LEN = 40


def slugify(title: str, *, is_home: bool = False) -> str:
    """Reduce a page title to a stable, filename-safe slug.

    The home page maps to ``index``; every other title is lowercased,
    ASCII-folded, hyphenated, stripped of punctuation, and truncated to 40 chars.
    A non-home title that would land on a reserved stem (``index``, the artifact
    stems) is disambiguated with a ``-page`` suffix so it can never clobber the
    design-system files or the home page.
    """
    if is_home:
        return HOME_SLUG

    # ASCII-fold accents (Café -> Cafe) by decomposing then dropping combining marks.
    folded = unicodedata.normalize("NFKD", title)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")

    # Lowercase, replace any run of non-alphanumerics with a single hyphen.
    hyphenated = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")

    slug = hyphenated[:_MAX_SLUG_LEN].strip("-") or "page"

    # A non-home page must not take a reserved stem.
    if slug in RESERVED_STEMS:
        slug = f"{slug}-page"
    return slug


def derive_page_map(page_titles) -> dict:
    """Derive ``{slug: {screenshot, expected_file}}`` from ordered page titles.

    The first title is the home page (-> ``index``); the rest are slugified.
    Collisions are resolved with a numeric suffix (``-2``, ``-3``, ...). Each slug
    derives its own ``<slug>.png`` and ``<slug>.html`` so the map is exactly the
    shape the emit/grader consume.
    """
    page_map: dict = {}
    used: set = set()
    for index, title in enumerate(page_titles):
        base = slugify(title, is_home=(index == 0))
        slug = _disambiguate(base, used)
        used.add(slug)
        page_map[slug] = {
            "screenshot": f"{slug}.png",
            "expected_file": f"{slug}.html",
        }
    return page_map


def _disambiguate(base: str, used: set) -> str:
    """Return ``base`` or the first ``base-N`` (N>=2) not already in ``used``."""
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"
