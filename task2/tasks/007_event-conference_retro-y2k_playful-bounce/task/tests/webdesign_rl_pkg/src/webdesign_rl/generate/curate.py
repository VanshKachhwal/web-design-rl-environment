"""Curation pure core: a downloaded batch -> survivor pool + coverage shortlist.

This is the AFK, testable core of the curation slice (issue 24). It mirrors
:mod:`modal_batch` — a pure, unit-tested core here + a thin I/O shell in
``scripts/curate.py`` (the filesystem copy + the report print). Nothing here
touches the network, Modal, or live generation; it operates purely on the
directory STRUCTURE of a downloaded batch.

A downloaded batch dir holds one seed dir per seed, named
``{index:03d}_{archetype}_{aesthetic}_{complexity}`` (the
:func:`~webdesign_rl.generate.modal_batch.seed_id` shape). A *survivor* is a seed
that emitted a Harbor task (a ``task/task.toml`` is present); a gate drop / error
leaves a ``site/`` but no ``task/``. The four steps:

- :func:`survivors` — the fully-emitted survivors, each parsed into a
  :class:`Survivor` record (id + seed tuple + dir path), sorted by id.
- :func:`dedupe_by_cell` — at most one survivor per ``(archetype, aesthetic)``
  cell, lowest index wins.
- :func:`select_coverage` — a greedy coverage shortlist: maximize distinct
  archetypes, then distinct aesthetics, while hitting a target complexity spread;
  best-effort (never crashes) when the pool can't satisfy the exact spread.
- :func:`coverage_report` / :func:`format_coverage_report` — an auditable
  summary of which taxonomy cells the shortlist covers vs misses, so the
  distribution claim is checkable rather than asserted.
"""

from dataclasses import dataclass
from pathlib import Path

from . import taxonomy

# The default coverage-shortlist size and its complexity spread (low/med/high in
# COMPLEXITIES order), per docs/design/task_selection.md: ~3 low / 4 med / 3 high
# for a legible easy<->hard grader curve across the final 10.
DEFAULT_SELECT_N = 10
DEFAULT_COMPLEXITY_SPREAD = (3, 4, 3)


@dataclass(frozen=True)
class Survivor:
    """One fully-emitted survivor, parsed from its batch seed-dir name.

    ``seed_id`` is the dir name (``{index:03d}_{archetype}_{aesthetic}_
    {complexity}``); ``archetype`` / ``aesthetic`` / ``complexity`` are parsed off
    it; ``path`` is the seed dir on disk (what the shell copies into the curated
    out dir).
    """

    seed_id: str
    archetype: str
    aesthetic: str
    complexity: str
    path: Path


def survivors(batch_dir):
    """Return the fully-emitted survivors under ``batch_dir``, sorted by id.

    A seed dir is a survivor iff it carries a ``task/task.toml`` (a gate drop /
    error leaves only ``site/`` and is excluded). The seed tuple is parsed from
    the dir name with ``split("_", 3)`` -> ``[index, archetype, aesthetic,
    complexity]`` (archetype/aesthetic use ``-``, never ``_``, so maxsplit-3 is
    exact). Sorted by ``seed_id`` so the index prefix gives a deterministic,
    batch-order pool.
    """
    batch_dir = Path(batch_dir)
    found = []
    for child in batch_dir.iterdir():
        if not child.is_dir():
            continue
        if not (child / "task" / "task.toml").exists():
            continue
        parts = child.name.split("_", 3)
        if len(parts) != 4:
            continue
        _index, archetype, aesthetic, complexity = parts
        found.append(Survivor(
            seed_id=child.name,
            archetype=archetype,
            aesthetic=aesthetic,
            complexity=complexity,
            path=child,
        ))
    found.sort(key=lambda s: s.seed_id)
    return found


def dedupe_by_cell(pool):
    """Keep at most one survivor per ``(archetype, aesthetic)`` cell.

    The lowest-index survivor wins: candidates are scanned in seed_id order (the
    index prefix orders them) so the first-seen per cell is the lowest index.
    The kept list stays in seed_id order; deterministic regardless of input
    order. Post-dedupe-aware sampling this is usually a no-op, but it stays as the
    dedupe guarantee the shortlist relies on.
    """
    seen = set()
    kept = []
    for s in sorted(pool, key=lambda s: s.seed_id):
        cell = (s.archetype, s.aesthetic)
        if cell in seen:
            continue
        seen.add(cell)
        kept.append(s)
    return kept


def select_coverage(pool, n=DEFAULT_SELECT_N,
                    complexity_spread=DEFAULT_COMPLEXITY_SPREAD):
    """Greedy coverage shortlist: at most ``n`` survivors spanning the taxonomy.

    Picks one survivor at a time, each time taking the candidate that best
    improves coverage — primarily a *new archetype*, then a *new aesthetic* —
    while respecting the target ``complexity_spread`` (the 3 numbers map to
    :data:`~webdesign_rl.generate.taxonomy.COMPLEXITIES` low/med/high). Same-cell
    candidates can't both be picked (the pool is deduped by cell first, so dedupe
    falls out of selection).

    Best-effort and crash-free: candidates whose complexity band is already at
    quota are deprioritized but NOT excluded, so when the pool can't meet the
    exact spread the shortlist still fills to ``n`` (or fewer, if the deduped pool
    is smaller) by best remaining coverage — the shortfall then shows up in
    :func:`coverage_report`. Deterministic: same pool -> same shortlist (ties
    break on seed_id).
    """
    pool = dedupe_by_cell(pool)
    quotas = dict(zip(taxonomy.COMPLEXITIES, complexity_spread))

    selected = []
    # Sort by seed_id so that among equally-desirable candidates ``max`` returns
    # the FIRST seen — the lowest seed_id (batch-order, deterministic) tie-break.
    remaining = sorted(pool, key=lambda s: s.seed_id)
    seen_archetypes = set()
    seen_aesthetics = set()
    band_counts = {band: 0 for band in taxonomy.COMPLEXITIES}

    while remaining and len(selected) < n:
        best = max(
            remaining,
            key=lambda s: _coverage_key(
                s, seen_archetypes, seen_aesthetics, band_counts, quotas
            ),
        )
        selected.append(best)
        remaining.remove(best)
        seen_archetypes.add(best.archetype)
        seen_aesthetics.add(best.aesthetic)
        band_counts[best.complexity] = band_counts.get(best.complexity, 0) + 1

    return selected


def _coverage_key(s, seen_archetypes, seen_aesthetics, band_counts, quotas):
    """Greedy desirability of picking ``s`` next (higher is better).

    Lexicographic, in priority order:
      1. the candidate's complexity band still has spread quota left,
      2. it introduces a new archetype (the primary coverage axis),
      3. it introduces a new aesthetic (the secondary axis).

    The seed_id tie-break is handled by scanning candidates in seed_id order, so
    ``max`` returns the lowest-id of any equally-scored set.
    """
    band_has_room = band_counts.get(s.complexity, 0) < quotas.get(s.complexity, 0)
    new_archetype = s.archetype not in seen_archetypes
    new_aesthetic = s.aesthetic not in seen_aesthetics
    return (band_has_room, new_archetype, new_aesthetic)


@dataclass(frozen=True)
class CoverageReport:
    """An auditable summary of which taxonomy cells a shortlist spans.

    ``archetypes_hit`` / ``archetypes_missed`` partition
    :data:`~webdesign_rl.generate.taxonomy.ARCHETYPES` by whether the shortlist
    covers them (same for aesthetics). ``complexity_spread`` is the realized
    low/med/high count (every band keyed, ``0`` when absent), so a spread
    shortfall is visible. ``selected`` is the shortlist size.
    """

    selected: int
    archetypes_hit: set
    archetypes_missed: set
    aesthetics_hit: set
    aesthetics_missed: set
    complexity_spread: dict


def coverage_report(selected):
    """Summarize which taxonomy cells ``selected`` covers vs misses.

    Pure over its input: derives the hit/missed archetype + aesthetic sets
    against the taxonomy and the realized complexity spread, so the "spans the
    distribution" claim is checkable rather than asserted.
    """
    selected = list(selected)
    archetypes_hit = {s.archetype for s in selected}
    aesthetics_hit = {s.aesthetic for s in selected}
    spread = {band: 0 for band in taxonomy.COMPLEXITIES}
    for s in selected:
        spread[s.complexity] = spread.get(s.complexity, 0) + 1
    return CoverageReport(
        selected=len(selected),
        archetypes_hit=archetypes_hit,
        archetypes_missed=set(taxonomy.ARCHETYPES) - archetypes_hit,
        aesthetics_hit=aesthetics_hit,
        aesthetics_missed=set(taxonomy.AESTHETICS) - aesthetics_hit,
        complexity_spread=spread,
    )


def format_coverage_report(report: CoverageReport) -> str:
    """A compact, log-friendly rendering of a :class:`CoverageReport`.

    Reuses the ``modal_batch._fmt_counts`` idiom for the spread line. Shows the
    covered/total tallies per axis and the realized complexity spread, so a
    shortfall reads off the text.
    """
    n_arch = len(taxonomy.ARCHETYPES)
    n_aes = len(taxonomy.AESTHETICS)
    lines = [
        f"curated: {report.selected} task(s)",
        f"  archetypes: {len(report.archetypes_hit)}/{n_arch} covered, "
        f"{len(report.archetypes_missed)} missed "
        f"({_fmt_set(report.archetypes_missed)})",
        f"  aesthetics: {len(report.aesthetics_hit)}/{n_aes} covered, "
        f"{len(report.aesthetics_missed)} missed "
        f"({_fmt_set(report.aesthetics_missed)})",
        f"  complexity spread: {_fmt_counts(report.complexity_spread)}",
    ]
    return "\n".join(lines)


def _fmt_counts(counts: dict) -> str:
    """Render a band->count map in COMPLEXITIES order (low/med/high)."""
    ordered = [
        (band, counts.get(band, 0)) for band in taxonomy.COMPLEXITIES
    ]
    extra = sorted(k for k in counts if k not in taxonomy.COMPLEXITIES)
    ordered += [(k, counts[k]) for k in extra]
    return ", ".join(f"{k}={v}" for k, v in ordered)


def _fmt_set(values) -> str:
    """Render a set of taxonomy tokens deterministically (sorted), or '(none)'."""
    if not values:
        return "none"
    return ", ".join(sorted(values))
