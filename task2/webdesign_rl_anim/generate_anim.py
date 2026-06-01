"""Single-shot focused generation of ONE rich, animated landing page.

This is the deliberately *non-scale* Task-2 generator: one API call producing one
self-contained, human-looking landing page whose animations are constrained to
the **CSS-only, timeline-seekable** class the deterministic filmstrip renderer can
capture (``render_anim.py``). The LLM boundary (streaming, retry, continuation) is
Task 1's :class:`AnthropicGenerationClient`, imported read-only.

The hard prompt constraints exist for grader determinism, not taste:
  * no JavaScript / ``requestAnimationFrame`` — only ``@keyframes`` + transitions,
  * finite entrance animations use ``animation-fill-mode: forwards`` (so the
    settled frame is the intended at-rest design),
  * at least one *continuous* loop and one *staggered* reveal (motion variety),
  * everything inline + offline (no CDNs / web fonts), since rendering blocks the
    network.
"""

import argparse
import json
import sys
from pathlib import Path

# Default creative brief if the caller passes none. Concrete enough to get a
# practical, content-rich page rather than lorem-ipsum.
DEFAULT_BRIEF = (
    "a product landing page for 'Aurora', a sleep & focus app — modern dark UI, "
    "an indigo-to-teal accent, clean geometric sans typography"
)

_PROMPT = """\
You are building ONE complete, production-quality **landing page** as a single \
self-contained HTML file. Theme: {brief}.

The page is a REFERENCE for an animation-replication benchmark, so its animation \
must be captured deterministically by seeking the timeline. Follow these rules \
EXACTLY:

CONTENT & LAYOUT (make it look like a real, human-designed site):
- A sticky/﻿top nav, a hero (headline + subcopy + two buttons + a visual element), \
a 3- or 4-card feature section, a stats/metrics row, a testimonial or CTA band, \
and a footer. Write real, specific copy — no lorem ipsum.
- One page only, named index.html. Desktop layout, ~1280px content width.

ANIMATION (this is what is graded — be deliberate and varied):
- Use ONLY CSS: @keyframes animations and CSS transitions. Absolutely NO \
JavaScript, NO requestAnimationFrame, NO <script> tags.
- Include a clear ENTRANCE for the hero (e.g. fade + slide-up), a STAGGERED reveal \
of the feature cards (each with a larger animation-delay than the last), and at \
least ONE CONTINUOUS looping animation (animation-iteration-count: infinite — e.g. \
a pulsing accent, a gradient shift, a floating shape).
- Finite (entrance/stagger) animations MUST use `animation-fill-mode: forwards` so \
the page holds its final designed state at rest.
- Keep entrance + stagger timing within ~1800ms total (durations + delays) so the \
motion is visible early; loops can be any period.

OFFLINE / DETERMINISM:
- Everything inline in the single file: put all CSS in one <style> block. No \
external stylesheets, no web-font links, no CDN scripts, no remote images. Use \
system font stacks and CSS-drawn shapes/gradients only (network is blocked at \
render time).

OUTPUT:
- Respond with the COMPLETE HTML document and NOTHING else (no commentary, no \
markdown fences). Start with <!doctype html> and end with </html>.
"""


def build_prompt(brief: str) -> str:
    return _PROMPT.format(brief=brief)


def _extract_html(text: str) -> str:
    """Pull the ``<!doctype …>…</html>`` document out of the model's reply.

    Tolerant of stray prose or accidental code fences: slices from the first
    ``<!doctype`` (or ``<html``) to the last ``</html>``.
    """
    low = text.lower()
    start = low.find("<!doctype")
    if start == -1:
        start = low.find("<html")
    end = low.rfind("</html>")
    if start == -1 or end == -1:
        raise ValueError("model response contained no <html> document")
    return text[start:end + len("</html>")]


def generate(client, brief: str, out_dir) -> Path:
    """Generate the animated landing page into ``out_dir`` and return its path.

    Writes ``index.html`` plus a ``page_map.json`` and ``seed.json`` so the
    directory is ready for the filmstrip renderer, grader, and Harbor emit.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html = _extract_html(client.complete(build_prompt(brief), temperature=0.7))
    (out_dir / "index.html").write_text(html)
    (out_dir / "page_map.json").write_text(json.dumps(
        {"index": {"expected_file": "index.html", "screenshot": "index.png"}},
        indent=2,
    ))
    (out_dir / "seed.json").write_text(json.dumps({"brief": brief, "part": 2}, indent=2))
    return out_dir / "index.html"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m webdesign_rl_anim.generate_anim",
        description="Generate one animated reference landing page (single API call).",
    )
    parser.add_argument("--out", required=True, help="Directory to write the site into.")
    parser.add_argument("--brief", default=DEFAULT_BRIEF,
                        help="Creative brief for the page theme/aesthetic.")
    args = parser.parse_args(argv)

    from webdesign_rl.generate.client import AnthropicGenerationClient

    path = generate(AnthropicGenerationClient(), args.brief, args.out)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
