"""Behavioral tests for the Modal batch runner's pure core (issue 06).

The batch runner fans the per-site gated pipeline out over the stratified seed
list on Modal. Modal itself is an untested, thin, lazy-imported shell; everything
that decides *what* happens — the deterministic ``seed_id``, the per-seed worker
that writes artifacts + emits a task and returns a structured ``SeedResult``, its
idempotent re-run, and the yield + per-check telemetry of ``summarize_batch`` —
is a pure core unit-tested here with a ``StubGenerationClient`` and an injected
fake render. No Modal, no network, no Docker.

We assert external behavior: artifacts on disk under ``<out_root>/<seed_id>/``,
the returned ``SeedResult``/``BatchReport``, and that the module imports without
the ``modal`` dependency installed.
"""

import json
from pathlib import Path

from PIL import Image

from webdesign_rl.generate.client import StubGenerationClient
from webdesign_rl.generate.seeds import sample_seeds
from webdesign_rl.generate import modal_batch

VIEWPORT = 1280


# --- A good, substantial 5-page site the stub feeds (mirrors orchestrator) --

_STAGE1 = {
    "brief": "A small architecture studio, bold editorial aesthetic.",
    "pages": [
        {"title": "Home", "sections": ["hero", "feature-grid", "card"]},
        {"title": "Studio", "sections": ["hero", "content-section", "card"]},
        {"title": "Projects", "sections": ["hero", "feature-grid", "card"]},
        {"title": "Process", "sections": ["hero", "content-section", "card"]},
        {"title": "Contact", "sections": ["hero", "contact-block", "card"]},
    ],
    "component_manifest": [
        "hero", "feature-grid", "content-section", "card", "contact-block",
    ],
}

_STAGE2 = (
    "===FILE variables.css===\n"
    ":root{--ink:#101010;--paper:#f4f1ea;--accent:#d6452b;--space:24px;"
    "--radius:6px;}\n"
    "===FILE components.css===\n"
    "body{margin:0;color:var(--ink);background:var(--paper);}"
    ".site-header{background:var(--ink);color:var(--paper);padding:var(--space);}"
    ".hero{padding:var(--space);background:var(--accent);color:var(--paper);}"
    ".feature-grid{display:grid;gap:var(--space);padding:var(--space);}"
    ".content-section{padding:var(--space);}"
    ".card{border-radius:var(--radius);padding:var(--space);"
    "background:var(--paper);}"
    ".contact-block{padding:var(--space);}\n"
    "===FILE header.html===\n"
    '<header class="site-header"><strong>FORM STUDIO</strong>'
    '<nav class="site-nav"><a href="index.html">Home</a></nav></header>\n'
    "===FILE footer.html===\n"
    '<footer class="site-footer">FORM STUDIO 2026</footer>\n'
)


def _body(title):
    return (
        '<main class="page">'
        f'<section class="hero"><h1>{title}</h1>'
        "<p>This is the page of a bold editorial architecture studio with real "
        "descriptive copy filling the layout meaningfully across several lines "
        "so the rendered page clears the substance floor comfortably.</p>"
        "</section>"
        '<section class="feature-grid">'
        '<div class="card"><h2>Selected Work</h2>'
        "<p>A curated set of recent residential and civic projects.</p></div>"
        "</section>"
        '<section class="content-section">'
        "<h2>Our Approach</h2>"
        "<p>We design calm, durable spaces grounded in their context.</p>"
        "</section></main>"
    )


_BAD_BODY = (
    '<main class="page"><section class="hero"><h1>Hi</h1>'
    "<p>Too short.</p></section></main>"
)

# A real taxonomy seed (the first stratified-sample point): run_one_seed calls
# expand_seed, so the axes must be real catalog values. The stub still overrides
# the stage outputs, so the gate sees the substantial 5-page _STAGE1 above.
_SEED = sample_seeds(1)[0]


def _solid(width=VIEWPORT, height=1400, color=(40, 60, 90)):
    img = Image.new("RGB", (width, height), (255, 255, 255))
    block = Image.new("RGB", (width, max(1, height // 2)), color)
    img.paste(block, (0, height // 4))
    return img


def _fake_render(site_dir, page_map, viewport=VIEWPORT):
    return {name: _solid() for name in page_map}


def _passing_responses():
    responses = [json.dumps(_STAGE1), _STAGE2]
    responses += [_body(p["title"]) for p in _STAGE1["pages"]]
    return responses


def _dropping_responses():
    # index starts thin and stays thin through one nudge -> dropped (budget 1).
    responses = [json.dumps(_STAGE1), _STAGE2]
    responses.append(_BAD_BODY)                       # index: initial, fails
    responses += [_body(p["title"]) for p in _STAGE1["pages"][1:]]
    responses.append(_BAD_BODY)                       # index: nudge #1, fails
    return responses


# --- seed_id: deterministic + collision-free -------------------------------

def test_seed_id_is_deterministic():
    s = sample_seeds(48)[7]
    assert modal_batch.seed_id(s, 7) == modal_batch.seed_id(s, 7)


def test_seed_id_is_filesystem_safe():
    sid = modal_batch.seed_id(_SEED, 3)
    assert sid and "/" not in sid and " " not in sid and ".." not in sid


def test_seed_id_unique_across_a_batch():
    seeds = sample_seeds(48)
    ids = [modal_batch.seed_id(s, i) for i, s in enumerate(seeds)]
    assert len(set(ids)) == len(ids)


def test_seed_id_encodes_the_index_for_ordering():
    seeds = sample_seeds(12)
    assert modal_batch.seed_id(seeds[0], 0).startswith("000")
    assert modal_batch.seed_id(seeds[5], 5).startswith("005")


# --- run_one_seed: a passing seed writes site/ + task/ ---------------------

def test_run_one_seed_passing_writes_site_and_task(tmp_path):
    client = StubGenerationClient(responses=_passing_responses())
    result = modal_batch.run_one_seed(
        _SEED, index=0, client=client, render=_fake_render, out_root=tmp_path
    )
    assert result.status == "passed"
    seed_dir = tmp_path / result.seed_id
    assert (seed_dir / "site" / "index.html").is_file()
    assert (seed_dir / "site" / "page_map.json").is_file()
    # The survivor is emitted as a runnable Harbor task.
    assert (seed_dir / "task" / "task.toml").is_file()
    assert (seed_dir / "task" / "tests" / "test.sh").is_file()
    assert result.task_dir == seed_dir / "task"


def test_run_one_seed_emit_false_skips_task(tmp_path):
    client = StubGenerationClient(responses=_passing_responses())
    result = modal_batch.run_one_seed(
        _SEED, index=0, client=client, render=_fake_render, out_root=tmp_path,
        emit=False,
    )
    assert result.status == "passed"
    assert not (tmp_path / result.seed_id / "task").exists()
    assert result.task_dir is None


def test_run_one_seed_records_components_used_from_manifest(tmp_path):
    # Issue 23: the per-seed component list is populated from the stage-1
    # manifest threaded through the pipeline stats, so summarize_batch can tally
    # which components actually got used across a batch.
    client = StubGenerationClient(responses=_passing_responses())
    result = modal_batch.run_one_seed(
        _SEED, index=0, client=client, render=_fake_render, out_root=tmp_path
    )
    assert result.status == "passed"
    assert set(result.components_used) == set(_STAGE1["component_manifest"])


# --- run_one_seed: a dropping seed records the fatal check ------------------

def test_run_one_seed_dropping_records_check_and_reason(tmp_path):
    client = StubGenerationClient(responses=_dropping_responses())
    result = modal_batch.run_one_seed(
        _SEED, index=1, client=client, render=_fake_render, out_root=tmp_path,
        max_nudges=1,
    )
    assert result.status == "dropped"
    assert result.check  # the fatal check name is populated
    assert result.reason
    # No task is emitted for a dropped seed; the site dir may exist but no task/.
    assert not (tmp_path / result.seed_id / "task").exists()


def test_run_one_seed_inline_drop_records_stage_check(tmp_path):
    # A too-short sitemap fails the stage-1 inline gate after re-rolls.
    short = {
        "brief": "Too small.",
        "pages": [{"title": "Home", "sections": ["hero"]}],
        "component_manifest": ["hero"],
    }
    responses = [json.dumps(short), json.dumps(short), json.dumps(short)]
    client = StubGenerationClient(responses=responses)
    result = modal_batch.run_one_seed(
        _SEED, index=2, client=client, render=_fake_render, out_root=tmp_path
    )
    assert result.status == "dropped"
    assert result.check is not None


# --- idempotent re-run: a re-run doesn't lose other seeds' dirs -------------

def test_rerun_is_addressable_and_preserves_other_seeds(tmp_path):
    # Run two distinct seeds, then re-run the first; the second's dir survives.
    seeds = sample_seeds(2)
    c0 = StubGenerationClient(responses=_passing_responses())
    c1 = StubGenerationClient(responses=_passing_responses())
    r0 = modal_batch.run_one_seed(
        seeds[0], index=0, client=c0, render=_fake_render, out_root=tmp_path
    )
    r1 = modal_batch.run_one_seed(
        seeds[1], index=1, client=c1, render=_fake_render, out_root=tmp_path
    )
    assert (tmp_path / r1.seed_id / "site" / "index.html").is_file()

    # Re-run seed 0; seed 1's artifacts must be untouched.
    c0b = StubGenerationClient(responses=_passing_responses())
    r0b = modal_batch.run_one_seed(
        seeds[0], index=0, client=c0b, render=_fake_render, out_root=tmp_path
    )
    assert r0b.seed_id == r0.seed_id
    assert r0b.status == "passed"
    assert (tmp_path / r0.seed_id / "site" / "index.html").is_file()
    assert (tmp_path / r0.seed_id / "task" / "task.toml").is_file()
    # The OTHER seed's directory was not clobbered or lost.
    assert (tmp_path / r1.seed_id / "site" / "index.html").is_file()
    assert (tmp_path / r1.seed_id / "task" / "task.toml").is_file()


# --- run_one_seed: an unexpected exception isolates as "errored" -----------

class _RaisingClient:
    """A GenerationClient whose ``.complete`` always raises mid-pipeline."""

    def __init__(self, exc):
        self._exc = exc

    def complete(self, prompt, *, temperature):
        raise self._exc


def test_run_one_seed_errors_isolate_as_errored_status(tmp_path):
    client = _RaisingClient(RuntimeError("API overloaded"))
    result = modal_batch.run_one_seed(
        _SEED, index=0, client=client, render=_fake_render, out_root=tmp_path
    )
    # No exception propagated; the seed is recorded as errored.
    assert result.status == "errored"
    assert result.check == "RuntimeError"
    assert "API overloaded" in result.reason


def test_run_one_seed_error_in_emit_isolates_as_errored(tmp_path):
    # A render that raises blows up at emit time (after the gate passed),
    # exercising the try/except around the emit body too.
    def _boom_render(site_dir, page_map, viewport=VIEWPORT):
        raise ValueError("render crashed")

    client = StubGenerationClient(responses=_passing_responses())
    result = modal_batch.run_one_seed(
        _SEED, index=0, client=client, render=_boom_render, out_root=tmp_path
    )
    assert result.status == "errored"
    assert result.check == "ValueError"
    assert "render crashed" in result.reason


def test_errored_seed_leaves_sibling_artifacts_intact(tmp_path):
    seeds = sample_seeds(2)
    # Seed 1 passes and writes a full site/.
    ok = StubGenerationClient(responses=_passing_responses())
    r_ok = modal_batch.run_one_seed(
        seeds[1], index=1, client=ok, render=_fake_render, out_root=tmp_path
    )
    assert (tmp_path / r_ok.seed_id / "site" / "index.html").is_file()

    # Seed 0 errors out; its sibling's artifacts must survive.
    boom = _RaisingClient(RuntimeError("blip"))
    r_err = modal_batch.run_one_seed(
        seeds[0], index=0, client=boom, render=_fake_render, out_root=tmp_path
    )
    assert r_err.status == "errored"
    assert (tmp_path / r_ok.seed_id / "site" / "index.html").is_file()


# --- summarize_batch: yield + per-check telemetry --------------------------

def _result(seed_id, status, check=None, nudges_by_check=None,
            components_used=None):
    return modal_batch.SeedResult(
        seed_id=seed_id,
        status=status,
        check=check,
        reason=None if status == "passed" else f"{check} failed",
        task_dir=None,
        nudges_by_check=nudges_by_check or {},
        components_used=components_used or [],
    )


def test_summarize_batch_computes_yield():
    results = [
        _result("a", "passed"),
        _result("b", "passed"),
        _result("c", "dropped", check="substance"),
        _result("d", "dropped", check="substance"),
    ]
    report = modal_batch.summarize_batch(results)
    assert report.total == 4
    assert report.passed == 2
    assert report.dropped == 2
    assert report.yield_fraction == 0.5


def test_summarize_batch_counts_drops_by_check():
    results = [
        _result("a", "passed"),
        _result("b", "dropped", check="substance"),
        _result("c", "dropped", check="substance"),
        _result("d", "dropped", check="token-compliance"),
    ]
    report = modal_batch.summarize_batch(results)
    assert report.drops_by_check == {"substance": 2, "token-compliance": 1}


def test_summarize_batch_aggregates_nudges_by_check():
    results = [
        _result("a", "passed", nudges_by_check={"substance": 2}),
        _result("b", "passed", nudges_by_check={"substance": 1, "chrome": 3}),
        _result("c", "dropped", check="token-compliance",
                nudges_by_check={"token-compliance": 5}),
    ]
    report = modal_batch.summarize_batch(results)
    assert report.nudges_by_check == {
        "substance": 3, "chrome": 3, "token-compliance": 5,
    }


def test_summarize_batch_tallies_components_used(tmp_path=None):
    # Issue 23: per-component usage telemetry — a count of how many seeds USED
    # each declared component (one increment per seed, dedup within a seed),
    # mirroring nudges_by_check. Proves whether the grammar diversified.
    results = [
        _result("a", "passed", components_used=["hero", "bento-grid"]),
        _result("b", "passed", components_used=["hero", "timeline"]),
        _result("c", "dropped", check="substance",
                components_used=["hero", "hero", "bento-grid"]),
    ]
    report = modal_batch.summarize_batch(results)
    assert report.components_used == {
        "hero": 3, "bento-grid": 2, "timeline": 1,
    }


def test_format_report_shows_components_used():
    results = [
        _result("a", "passed", components_used=["hero", "bento-grid"]),
    ]
    report = modal_batch.summarize_batch(results)
    text = modal_batch.format_report(report)
    assert "bento-grid" in text


def test_summarize_batch_empty_is_zero_yield():
    report = modal_batch.summarize_batch([])
    assert report.total == 0
    assert report.passed == 0
    assert report.yield_fraction == 0.0


def test_summarize_batch_counts_errored_distinctly_from_dropped():
    results = [
        _result("a", "passed"),
        _result("b", "passed"),
        _result("c", "dropped", check="substance"),
        _result("d", "errored", check="RuntimeError"),
        _result("e", "errored", check="ValueError"),
        _result("f", "errored", check="RuntimeError"),
    ]
    report = modal_batch.summarize_batch(results)
    assert report.total == 6
    assert report.passed == 2
    # dropped counts ONLY gate drops now, not errors.
    assert report.dropped == 1
    assert report.errored == 3
    assert report.passed + report.dropped + report.errored == report.total
    # Yield is still passed / total, unaffected by the errored split.
    assert report.yield_fraction == 2 / 6
    assert report.errors_by_type == {"RuntimeError": 2, "ValueError": 1}
    # An errored seed is NOT counted as a gate drop.
    assert report.drops_by_check == {"substance": 1}


def test_format_report_shows_errored_count_and_types():
    results = [
        _result("a", "passed"),
        _result("b", "dropped", check="substance"),
        _result("c", "errored", check="RuntimeError"),
    ]
    report = modal_batch.summarize_batch(results)
    text = modal_batch.format_report(report)
    assert "errored" in text.lower()
    assert "RuntimeError" in text


# --- import-safety: the module imports without `modal` installed -----------

def test_module_imports_without_modal():
    import importlib
    import webdesign_rl.generate.modal_batch as mb

    importlib.reload(mb)  # re-importing must not require `modal`
    assert hasattr(mb, "run_one_seed")
    assert hasattr(mb, "summarize_batch")
    assert hasattr(mb, "seed_id")


# --- the generation-batch default concurrency matches the eval default -------

def test_default_concurrency_is_ten():
    # Decided policy (eval-pipeline design): concurrency = 10 at both ends of the
    # pipeline — generation and eval — under the single shared Anthropic key.
    assert modal_batch.DEFAULT_CONCURRENCY == 10
