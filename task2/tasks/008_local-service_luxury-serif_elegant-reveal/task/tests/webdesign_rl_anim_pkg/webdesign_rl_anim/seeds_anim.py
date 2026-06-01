"""Diversity seeds for the animated batch — *soft steers*, not constraints.

The two-pass generator (``two_pass.py``) lets the LLM decide the sitemap and
structure freely (no component catalog / manifest). Seeds exist ONLY to spread a
batch across site types so 24 generations don't mode-collapse into a dozen
near-identical SaaS pages — the brief's "good distribution of website types".

Reuses Task 1's deterministic grid-spanning sampler read-only for the
``archetype × aesthetic`` span, and adds an **animation-style** axis for motion
diversity. The expanded seed is a flat *steer dict* threaded into the Pass-1
prompt as creative direction; nothing here forces a page set, page count, or
component list (the model owns those, told to produce 5 pages).
"""

from webdesign_rl.generate.seeds import sample_seeds

# The animation-style axis: (name, prompt hint). Sampled round-robin per seed so a
# batch spans distinct motion characters regardless of archetype/aesthetic.
ANIMATION_STYLES = (
    ("smooth-fade", "gentle fades and soft slide-ups; calm, eased, unhurried motion"),
    ("snappy-slide", "quick, confident slide-ins with crisp easing; energetic but tight"),
    ("playful-bounce", "springy overshoot/bounce and scale-pops; fun and lively"),
    ("elegant-reveal", "refined staggered reveals, subtle blur-to-sharp and rise; premium feel"),
    ("kinetic-loop", "prominent continuous loops (pulses, drifting gradients, float) over a clean entrance"),
)


PAGE_COUNT = 5  # Task 2 generates 5-page sites for now.


def sample_anim_seeds(count: int):
    """Return ``count`` ``(Seed, animation_style_name)`` pairs spanning the grid.

    Archetype × aesthetic span is Task 1's deterministic walk; the animation style
    is round-robined so it spreads across the batch independently of the design
    cell. Same ``count`` → identical list. (Complexity from Task 1's sampler is
    ignored — page count is fixed at :data:`PAGE_COUNT` and the model owns the
    actual page set.)
    """
    pairs = []
    for i, seed in enumerate(sample_seeds(count)):
        style = ANIMATION_STYLES[i % len(ANIMATION_STYLES)][0]
        pairs.append((seed, style))
    return pairs


def steer(seed, animation_style: str) -> dict:
    """A flat creative-steer dict for the Pass-1 prompt (provenance, not constraint).

    Carries the soft direction (archetype/aesthetic/audience/mood/animation style)
    and the target page count. No page set, no component catalog — the model owns
    structure. ``seed_tuple`` records full provenance for curation/audit.
    """
    style_hint = dict(ANIMATION_STYLES).get(animation_style, "")
    return {
        "archetype": seed.archetype,
        "aesthetic": seed.aesthetic,
        "audience": seed.audience,
        "brand_mood": seed.brand_mood,
        "animation_style": animation_style,
        "animation_style_hint": style_hint,
        "page_count": PAGE_COUNT,
        "seed_tuple": list(seed) + [animation_style],
    }
