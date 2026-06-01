"""The font palette manifest — the single source of truth for typography.

One curated palette, declared **once**, feeding three consumers that must never
diverge (or determinism vs. fidelity splits again — see ``generator_design.md`` →
"Inherited constraint: the generator owns the font palette"):

1. **The verifier/render image install** (``emit.templates.verifier_dockerfile``)
   — :data:`INSTALL_FONTS` is the list of pinned ``.ttf`` files fetched from the
   ``google/fonts`` GitHub repo at a pinned commit during ``docker build`` (which
   has network); the render itself stays offline. Each lands in
   ``/usr/share/fonts`` + ``fc-cache`` so the family resolves by **bare family
   name** (the agent never receives the ``.ttf``, so its ``font-family: Inter``
   must resolve OS-level — no ``@font-face`` from a site bundle).
2. **The generator's allowed ``font-family`` set** (stage-2 prompt) — generation
   may only pick from :func:`allowed_families`.
3. **The gate's font-palette check** (``quality_gate``) — any ``font-family``
   outside :func:`allowed_families` fails the site.

Design decision #6: 8 OFL families + DejaVu fallback; **display faces are
headings-only**.
"""

from dataclasses import dataclass

# DejaVu is already installed in the base image (apt ``fonts-dejavu-core``) and
# is the deterministic fallback every family degrades to identically. It is an
# allowed family but is not fetched by :data:`INSTALL_FONTS` (apt owns it).
FALLBACK_FAMILY = "DejaVu Sans"

# Generic CSS family keywords are always allowed in a `font-family` stack — they
# are not external resources, they just name a category the browser fills from
# whatever is installed (which, deterministically, is our palette + DejaVu).
GENERIC_FAMILIES = frozenset(
    {"serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif",
     "ui-serif", "ui-monospace", "cursive", "fantasy", "inherit", "initial"}
)


@dataclass(frozen=True)
class FontFace:
    """One palette family + how to install it OS-level.

    ``family`` is the bare CSS family name a site references. ``ttf_path`` is the
    file's path inside the ``google/fonts`` repo (under ``ofl/``); it is fetched
    raw at :data:`PINNED_FONTS_SHA` during image build. ``headings_only`` marks a
    display face the generator may use for headings only, never body text.
    """

    family: str
    ttf_path: str
    headings_only: bool = False


# The ``google/fonts`` commit the .ttf files are pinned to. Build-time fetch from
# raw.githubusercontent.com at this SHA is reproducible; bumping the palette
# means bumping this SHA (and re-confirming the paths still resolve). Verified
# all nine raw URLs return 200 at this SHA.
PINNED_FONTS_SHA = "fafaa09e4abf799c185f85e9b6eacb7db31ca5ed"

# The curated palette. Most families ship as a single variable .ttf
# (``Family[wght].ttf``) which fontconfig exposes under the bare family name;
# Anton and Poppins ship static instances (Anton has only a Regular; Poppins'
# variable axis was dropped upstream, so we take its Regular). Display faces
# (Archivo's heavy register via Anton, and Playfair Display) are headings-only.
PALETTE = (
    FontFace("Inter", "ofl/inter/Inter[opsz,wght].ttf"),
    FontFace("Work Sans", "ofl/worksans/WorkSans[wght].ttf"),
    FontFace("Space Grotesk", "ofl/spacegrotesk/SpaceGrotesk[wght].ttf"),
    FontFace("Archivo", "ofl/archivo/Archivo[wdth,wght].ttf"),
    # Anton is the heavy/display register called for in decision #6
    # ("Archivo(+heavy/Anton)"); it only exists as a display weight.
    FontFace("Anton", "ofl/anton/Anton-Regular.ttf", headings_only=True),
    FontFace("Playfair Display", "ofl/playfairdisplay/PlayfairDisplay[wght].ttf",
             headings_only=True),
    FontFace("Source Serif 4", "ofl/sourceserif4/SourceSerif4[opsz,wght].ttf"),
    FontFace("Poppins", "ofl/poppins/Poppins-Regular.ttf"),
    FontFace("JetBrains Mono", "ofl/jetbrainsmono/JetBrainsMono[wght].ttf"),
)

# The bare family names of the palette, in declaration order.
PALETTE_FAMILIES = tuple(face.family for face in PALETTE)

# Display faces a site may use for headings only, never body copy.
HEADINGS_ONLY = frozenset(face.family for face in PALETTE if face.headings_only)


def allowed_families():
    """Every ``font-family`` value a generated site may legally name.

    The palette (resolved OS-level), the DejaVu fallback, and the generic CSS
    family keywords. Anything else fails the gate's font-palette check — it would
    silently fall back to DejaVu in the offline render, so the typography the
    agent studies would not be the one the design intended.
    """
    return set(PALETTE_FAMILIES) | {FALLBACK_FAMILY} | set(GENERIC_FAMILIES)


def install_urls():
    """Raw ``google/fonts`` URLs for every palette ``.ttf``, pinned to a SHA.

    The verifier-image build fetches these (build-time has network) into
    ``/usr/share/fonts`` then runs ``fc-cache``; the render stays offline. DejaVu
    is excluded — apt already installs it in the base image.
    """
    base = f"https://raw.githubusercontent.com/google/fonts/{PINNED_FONTS_SHA}"
    return [f"{base}/{face.ttf_path}" for face in PALETTE]


# Where the palette .ttf files are installed so fontconfig resolves them by bare
# family name (no @font-face; the agent's `font-family: Inter` must resolve
# OS-level since it never receives the .ttf).
INSTALL_FONT_DIR = "/usr/share/fonts/truetype/webdesign-palette"


def dockerfile_install_block():
    """The Dockerfile ``RUN`` block that fetches + installs the curated palette.

    Build-time fetch (``docker build`` has network; the render at grade time is
    offline) of each pinned ``.ttf`` into :data:`INSTALL_FONT_DIR`, then
    ``fc-cache -f`` so every family resolves by bare name. Both the emitted
    verifier image and the in-container agent-screenshot render image build their
    font layer from this one block, so they can never drift. Requires ``curl``.
    """
    # ``-g`` (--globoff) is mandatory: several palette files are variable fonts
    # whose names contain ``[wght]`` etc., which curl would otherwise misread as a
    # URL glob range and fail. ``--retry`` rides out transient build-time blips.
    fetches = " \\\n".join(
        f'    && curl -fsSL --globoff --retry 3 -o '
        f'"{INSTALL_FONT_DIR}/{url.rsplit("/", 1)[-1]}" "{url}"'
        for url in install_urls()
    )
    return (
        "# The curated font palette (issue 05), installed OS-level so a site's\n"
        "# `font-family: Inter` resolves by bare name rather than falling back to\n"
        "# DejaVu. Pinned .ttf files are fetched from google/fonts at a fixed\n"
        f"# commit ({PINNED_FONTS_SHA}) during build (build-time has\n"
        "# network; the render at grade time stays offline), then fc-cache'd.\n"
        f"RUN mkdir -p {INSTALL_FONT_DIR} \\\n"
        f"{fetches} \\\n"
        "    && fc-cache -f"
    )
