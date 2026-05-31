"""Behavioral tests for the fonts manifest — the single source of truth.

The manifest (``webdesign_rl.generate.fonts``) is the one place the font palette
is declared. It feeds three consumers that must never diverge: the verifier
image's OS-level install list, the generator's allowed ``font-family`` set, and
the gate's font-palette check. These tests pin the manifest's public surface —
the families, the headings-only display set, the fallback, the allowed-family
set generation may use, and the pinned install URLs the Dockerfile fetches.
"""

from webdesign_rl.generate import fonts


def test_palette_lists_the_eight_design_doc_families():
    # Decision #6: the curated 8 OFL families. Bare family names exactly as a
    # site's `font-family` would reference them (so they resolve OS-level).
    expected = {
        "Inter",
        "Work Sans",
        "Space Grotesk",
        "Archivo",
        "Playfair Display",
        "Source Serif 4",
        "Poppins",
        "JetBrains Mono",
    }
    assert expected <= set(fonts.PALETTE_FAMILIES)


def test_display_faces_are_headings_only():
    # The display register (Anton — the Archivo "heavy" — and Playfair Display)
    # is for headings only, never body copy.
    assert "Playfair Display" in fonts.HEADINGS_ONLY
    assert "Anton" in fonts.HEADINGS_ONLY
    # A workhorse text face is NOT headings-only.
    assert "Inter" not in fonts.HEADINGS_ONLY


def test_fallback_is_dejavu_and_is_an_allowed_family():
    # DejaVu is the deterministic fallback every family degrades to identically;
    # it remains a legal family even though apt (not the fetch) installs it.
    assert "DejaVu" in fonts.FALLBACK_FAMILY
    assert fonts.FALLBACK_FAMILY in fonts.allowed_families()


def test_allowed_families_includes_palette_and_generic_keywords():
    allowed = fonts.allowed_families()
    assert set(fonts.PALETTE_FAMILIES) <= allowed
    # Generic CSS keywords are not external resources and are always permitted.
    assert "sans-serif" in allowed
    assert "serif" in allowed
    assert "monospace" in allowed
    # A non-palette real family is NOT allowed.
    assert "Comic Sans MS" not in allowed


def test_install_urls_are_pinned_to_a_commit_sha_one_per_family():
    urls = fonts.install_urls()
    # One fetchable .ttf per palette family (DejaVu excluded — apt installs it).
    assert len(urls) == len(fonts.PALETTE_FAMILIES)
    for url in urls:
        # Pinned to a specific commit SHA (not a moving branch), raw host, .ttf.
        assert url.startswith(
            f"https://raw.githubusercontent.com/google/fonts/"
            f"{fonts.PINNED_FONTS_SHA}/"
        )
        assert url.endswith(".ttf")
    # The SHA is a real 40-char git hash, not a branch name like "main".
    assert len(fonts.PINNED_FONTS_SHA) == 40


def test_dockerfile_install_block_disables_curl_url_globbing():
    # Several palette files are variable fonts with [wght]/[opsz,wght] in their
    # names; curl reads unquoted brackets as a URL glob range and fails the build.
    # The install block MUST pass -g / --globoff (regression guard for that bug).
    block = fonts.dockerfile_install_block()
    assert "curl" in block
    assert "-g" in block or "--globoff" in block
    # It installs where fontconfig sees them and refreshes the cache.
    assert fonts.INSTALL_FONT_DIR in block
    assert "fc-cache" in block
    # Every palette URL is fetched.
    for url in fonts.install_urls():
        assert url in block
