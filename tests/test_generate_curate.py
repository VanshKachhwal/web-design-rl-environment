"""Behavioral tests for the curation pure core (issue 24).

Curation turns a downloaded generation batch into a survivor pool and a
coverage-maximizing shortlist. The filesystem copy + CLI are a thin, untested
shell; everything that *decides what is kept and reported* — the survivor filter
(``survivors``), the per-cell dedupe (``dedupe_by_cell``), the greedy coverage
shortlist (``select_coverage``), and the auditable distribution summary
(``coverage_report`` / ``format_coverage_report``) — is the pure core unit-tested
here against a SYNTHETIC fixture pool. No network, no Modal, no live generation.

The synthetic pool is just directory STRUCTURE: a seed dir named
``{index:03d}_{archetype}_{aesthetic}_{complexity}`` (the ``modal_batch.seed_id``
shape) is a *survivor* iff it has a ``task/task.toml``, and a *drop* if it has
only ``site/`` (no ``task/``). No real sites are written.
"""

from collections import Counter
from pathlib import Path

from webdesign_rl.generate import curate, taxonomy


def _seed_dir(batch_dir: Path, name: str, *, survivor: bool) -> Path:
    """Create one synthetic seed dir; a survivor gets ``task/task.toml``, a drop
    gets only ``site/``."""
    d = batch_dir / name
    (d / "site").mkdir(parents=True)
    if survivor:
        (d / "task").mkdir()
        (d / "task" / "task.toml").write_text("")
    return d


def _pool(batch_dir: Path, survivors, drops=()):
    """Build a synthetic batch dir from survivor + drop dir-name lists."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    for name in survivors:
        _seed_dir(batch_dir, name, survivor=True)
    for name in drops:
        _seed_dir(batch_dir, name, survivor=False)
    return batch_dir


def test_survivors_excludes_drop_only_dirs(tmp_path):
    """A dir with task/task.toml is a survivor; a dir with only site/ is excluded."""
    batch = _pool(
        tmp_path / "batch",
        survivors=["000_saas-landing_swiss-editorial_low"],
        drops=["001_agency-portfolio_brutalist_med"],
    )

    result = curate.survivors(batch)

    ids = [s.seed_id for s in result]
    assert ids == ["000_saas-landing_swiss-editorial_low"]


def test_survivors_parse_seed_tuple_with_hyphenated_tokens(tmp_path):
    """The seed tuple is parsed off the dir name; hyphenated archetype/aesthetic
    tokens survive the maxsplit-3 split intact, and survivors sort by seed_id."""
    batch = _pool(
        tmp_path / "batch",
        survivors=[
            "002_editorial-blog_corporate-flat_high",
            "000_saas-landing_swiss-editorial_low",
        ],
    )

    result = curate.survivors(batch)

    assert [s.seed_id for s in result] == [
        "000_saas-landing_swiss-editorial_low",
        "002_editorial-blog_corporate-flat_high",
    ]
    first = result[0]
    assert (first.archetype, first.aesthetic, first.complexity) == (
        "saas-landing", "swiss-editorial", "low",
    )
    assert first.path == batch / "000_saas-landing_swiss-editorial_low"


def _name(index, archetype, aesthetic, complexity):
    return f"{index:03d}_{archetype}_{aesthetic}_{complexity}"


def _rich_pool_names(spread=("low", "low", "low", "med", "med", "med", "med",
                             "high", "high", "high")):
    """10 survivor dir names, each a distinct archetype + distinct aesthetic,
    with complexities matching ``spread`` (default the 3/4/3 target order)."""
    return [
        _name(i, taxonomy.ARCHETYPES[i], taxonomy.AESTHETICS[i], spread[i])
        for i in range(10)
    ]


def test_dedupe_by_cell_keeps_lowest_index_per_cell(tmp_path):
    """Two survivors in one (archetype, aesthetic) cell collapse to one — the
    lowest-index (sorted-first) survivor — while other cells pass through."""
    batch = _pool(
        tmp_path / "batch",
        survivors=[
            "000_saas-landing_swiss-editorial_low",
            "005_saas-landing_swiss-editorial_high",  # same cell as 000
            "002_agency-portfolio_brutalist_med",
        ],
    )

    deduped = curate.dedupe_by_cell(curate.survivors(batch))

    assert [s.seed_id for s in deduped] == [
        "000_saas-landing_swiss-editorial_low",
        "002_agency-portfolio_brutalist_med",
    ]


def test_select_coverage_distinct_cells_and_target_spread(tmp_path):
    """A rich pool yields n=10 survivors with 10 distinct archetypes, 10 distinct
    aesthetics, and the 3/4/3 (low/med/high) complexity spread."""
    batch = _pool(tmp_path / "batch", survivors=_rich_pool_names())

    selected = curate.select_coverage(curate.survivors(batch), n=10)

    assert len(selected) == 10
    assert len({s.archetype for s in selected}) == 10
    assert len({s.aesthetic for s in selected}) == 10
    spread = Counter(s.complexity for s in selected)
    assert (spread["low"], spread["med"], spread["high"]) == (3, 4, 3)


def test_select_coverage_best_effort_when_spread_unsatisfiable(tmp_path):
    """When the pool can't meet the spread (all 'low'), select still fills to n
    by best remaining coverage without crashing — realized spread is all 'low'."""
    names = [
        _name(i, taxonomy.ARCHETYPES[i], taxonomy.AESTHETICS[i], "low")
        for i in range(10)
    ]
    batch = _pool(tmp_path / "batch", survivors=names)

    selected = curate.select_coverage(curate.survivors(batch), n=10)

    assert len(selected) == 10
    assert len({s.archetype for s in selected}) == 10
    assert all(s.complexity == "low" for s in selected)


def test_select_coverage_caps_at_pool_size(tmp_path):
    """A pool smaller than n returns the whole (deduped) pool, never crashing."""
    names = _rich_pool_names()[:4]
    batch = _pool(tmp_path / "batch", survivors=names)

    selected = curate.select_coverage(curate.survivors(batch), n=10)

    assert len(selected) == 4


def test_select_coverage_is_deterministic(tmp_path):
    """Same pool -> same shortlist, including order (no RNG)."""
    batch = _pool(tmp_path / "batch", survivors=_rich_pool_names())
    pool = curate.survivors(batch)

    first = curate.select_coverage(pool, n=7)
    second = curate.select_coverage(pool, n=7)

    assert [s.seed_id for s in first] == [s.seed_id for s in second]


def test_coverage_report_names_covered_and_missed_cells(tmp_path):
    """The report lists archetypes/aesthetics hit vs missed (against the taxonomy)
    and the realized complexity spread."""
    names = [
        _name(0, taxonomy.ARCHETYPES[0], taxonomy.AESTHETICS[0], "low"),
        _name(1, taxonomy.ARCHETYPES[1], taxonomy.AESTHETICS[1], "med"),
        _name(2, taxonomy.ARCHETYPES[2], taxonomy.AESTHETICS[2], "med"),
    ]
    batch = _pool(tmp_path / "batch", survivors=names)
    selected = curate.survivors(batch)

    report = curate.coverage_report(selected)

    assert report.archetypes_hit == set(taxonomy.ARCHETYPES[:3])
    assert report.archetypes_missed == set(taxonomy.ARCHETYPES[3:])
    assert report.aesthetics_hit == set(taxonomy.AESTHETICS[:3])
    assert report.aesthetics_missed == set(taxonomy.AESTHETICS[3:])
    assert report.complexity_spread == {"low": 1, "med": 2, "high": 0}
    assert report.selected == 3


def test_format_coverage_report_is_a_string_with_shortfall_visible(tmp_path):
    """The formatted report renders the realized spread + the missed-cell counts,
    so a shortfall (e.g. only 'low') is auditable in the text."""
    names = [
        _name(i, taxonomy.ARCHETYPES[i], taxonomy.AESTHETICS[i], "low")
        for i in range(3)
    ]
    batch = _pool(tmp_path / "batch", survivors=names)
    report = curate.coverage_report(curate.survivors(batch))

    text = curate.format_coverage_report(report)

    assert isinstance(text, str)
    assert "low" in text
    # 3 of 10 archetypes / aesthetics covered -> 7 missed each, surfaced in text.
    assert "7" in text


def test_curate_module_is_import_safe_without_modal():
    """The pure core imports with no Modal/network deps — it only reaches into
    the taxonomy. Re-importing must not pull in any heavy/optional dependency."""
    import importlib

    module = importlib.import_module("webdesign_rl.generate.curate")
    importlib.reload(module)
    # The public surface is present.
    for name in ("survivors", "dedupe_by_cell", "select_coverage",
                 "coverage_report", "format_coverage_report"):
        assert hasattr(module, name)
