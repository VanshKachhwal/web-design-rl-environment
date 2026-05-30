"""Orchestrate the 3-stage pipeline into a renderable site directory.

``generate_site(seed, client, out_dir)`` runs stage 1 -> stage 2 -> stage 3
(fanned out per page) through the stubbable
:class:`~webdesign_rl.generate.client.GenerationClient`, then **assembles** the
results into a static HTML/CSS site on disk:

- ``variables.css`` + ``components.css`` — the frozen design-system stylesheets.
- one ``<slug>.html`` per sitemap page, each a full document that links *only*
  those two stylesheets and injects the header/nav/footer partials
  **byte-identically** (so chrome is provably identical across pages) around the
  stage-3 body markup.
- ``page_map.json`` — the ``{slug: {screenshot, expected_file}}`` map (derived in
  code from the sitemap) in the exact shape the emit/grader consume.

Consistency is by construction: every page links the same frozen stylesheets and
embeds the same chrome, so no page can drift the palette, components, or
navigation. This is the minimal end-to-end skeleton (issue 01); the quality gate,
repair loop, and Modal fan-out deepen this seam in later slices.
"""

import json
from pathlib import Path

from . import stages

# The two frozen stylesheets every page links — and the *only* stylesheets a page
# may reference (the token/manifest-compliance contract).
VARIABLES_CSS = "variables.css"
COMPONENTS_CSS = "components.css"


def generate_site(seed, client, out_dir) -> Path:
    """Run the 3-stage pipeline and write a renderable site to ``out_dir``.

    Args:
        seed: a sampled seed dict (archetype/aesthetic/complexity/…). Stage 1
            designs the site *around* this; diversity comes from the seed, not the
            model's variance.
        client: a :class:`GenerationClient` (stub in tests, Anthropic in prod).
        out_dir: directory to write the site into (created if absent).

    Returns:
        The ``Path`` to the written site directory. It contains the two frozen
        stylesheets, one HTML file per page, ``page_map.json``, and
        ``seed.json`` (the recorded seed tuple).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = stages.run_stage1(seed, client)
    design = stages.run_stage2(spec, client)

    # Stage 2 artifacts are frozen to disk once; every page links them.
    (out_dir / VARIABLES_CSS).write_text(design.variables_css)
    (out_dir / COMPONENTS_CSS).write_text(design.components_css)

    for page in spec.pages:
        body = stages.run_stage3(spec, design, page, client)
        html = _assemble_page(page["title"], body, design)
        (out_dir / f"{page['slug']}.html").write_text(html)

    (out_dir / "page_map.json").write_text(json.dumps(spec.page_map, indent=2))

    # Record the seed for auditability and curation: the whole sampled dict
    # (axes + free modifiers + the recorded ``seed_tuple``) is what makes the
    # batch auditable, re-runnable, and a cheap diversity signal for curation.
    (out_dir / "seed.json").write_text(json.dumps(seed, indent=2))
    return out_dir


def _assemble_page(title: str, body: str, design: stages.DesignSystem) -> str:
    """Wrap stage-3 body markup into a full, hermetic, static HTML document.

    Links only the two frozen stylesheets and injects the header/nav/footer
    partials byte-identically (the same strings for every page), so chrome
    identity and stylesheet-only referencing hold by construction.
    """
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=1280">\n'
        f"<title>{title}</title>\n"
        f'<link rel="stylesheet" href="{VARIABLES_CSS}">\n'
        f'<link rel="stylesheet" href="{COMPONENTS_CSS}">\n'
        "</head>\n"
        "<body>\n"
        f"{design.header_html}\n"
        f"{design.nav_html}\n"
        f"{body}\n"
        f"{design.footer_html}\n"
        "</body>\n"
        "</html>\n"
    )
