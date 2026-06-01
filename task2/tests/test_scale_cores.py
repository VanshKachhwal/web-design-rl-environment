"""Deterministic unit tests for the scaling pipeline's pure cores (no API/Modal).

Same split as before: stochastic/IO (LLM, Playwright, Modal, Harbor) is untested
shell; the deterministic logic is unit-tested here. The lean gate is exercised with
a stub filmstrip-render (canned PIL frames), no Chromium.
"""

import json

import pytest
from PIL import Image

from webdesign_rl_anim.curate_anim import curate
from webdesign_rl_anim.evaluate_anim import _flip_agent_internet
from webdesign_rl_anim.gate_anim_lean import run_lean_gate
from webdesign_rl_anim.seeds_anim import ANIMATION_STYLES, sample_anim_seeds, steer
from webdesign_rl_anim.two_pass import (
    Plan,
    PlanError,
    _derive_pages,
    parse_blocks,
    run_plan,
)


# ---- seeds (soft steer + determinism) --------------------------------------

def test_sample_anim_seeds_is_deterministic_and_spreads():
    a = sample_anim_seeds(10)
    b = sample_anim_seeds(10)
    assert [(s.archetype, s.aesthetic, st) for s, st in a] == \
           [(s.archetype, s.aesthetic, st) for s, st in b]
    # animation style round-robins across the batch
    assert len({st for _, st in a}) == min(10, len(ANIMATION_STYLES))


def test_steer_has_soft_fields_no_constraints():
    seed, style = sample_anim_seeds(1)[0]
    s = steer(seed, style)
    assert s["page_count"] == 5
    assert s["animation_style"] == style
    assert s["seed_tuple"][-1] == style
    assert "component_catalog" not in s and "pages" not in s  # no structural constraint


# ---- two-pass parsing ------------------------------------------------------

def test_parse_blocks_splits_plan_and_files():
    raw = ("===PLAN===\n{\"x\":1}\n===FILE styles.css===\nbody{}\n"
           "===FILE animations.css===\n.a{}\n")
    b = parse_blocks(raw)
    assert b["PLAN"] == '{"x":1}'
    assert b["styles.css"] == "body{}"
    assert b["animations.css"] == ".a{}"


def test_derive_pages_home_is_index_and_slugs_unique():
    pages = _derive_pages(["Home", "Our Work", "Our Work", "Contact Us"])
    slugs = [p["slug"] for p in pages]
    assert slugs[0] == "index"
    assert slugs == ["index", "our-work", "our-work-2", "contact-us"]


class _PlanStub:
    def __init__(self, raw):
        self.raw = raw
    def complete(self, prompt, *, temperature):
        return self.raw


def test_run_plan_builds_plan_from_blocks():
    raw = ('===PLAN===\n{"brief":"b","pages":["Home","About"]}\n'
           '===FILE styles.css===\nbody{}\n===FILE animations.css===\n'
           '@keyframes r{}\n.anim-rise{}\n===FILE header.html===\n<header></header>\n'
           '===FILE footer.html===\n<footer></footer>')
    plan = run_plan({}, _PlanStub(raw))
    assert plan.brief == "b"
    assert [p["slug"] for p in plan.pages] == ["index", "about"]
    assert "anim-rise" in plan.animations_css
    assert set(plan.page_map) == {"index", "about"}


def test_run_plan_raises_on_missing_shared_files():
    raw = '===PLAN===\n{"brief":"b","pages":["Home","About"]}\n===FILE styles.css===\nbody{}'
    with pytest.raises(PlanError):
        run_plan({}, _PlanStub(raw))


# ---- lean gate (stub render) -----------------------------------------------

def _plan_one_page(tmp_path):
    (tmp_path / "styles.css").write_text("body{}")
    (tmp_path / "animations.css").write_text(".anim-rise{}")
    (tmp_path / "index.html").write_text("<html><body><main>hi</main></body></html>")
    return Plan(brief="", pages=[{"slug": "index", "title": "Home"}],
                styles_css="", animations_css="", header_html="", footer_html="")


def _frames(varying):
    a = Image.new("RGB", (80, 120), (10, 10, 10))
    b = Image.new("RGB", (80, 120), (240, 240, 240) if varying else (10, 10, 10))
    return [a, b, a]


def _nonblank():
    """A non-uniform (top-light/bottom-dark) image: luminance std above the blank floor."""
    img = Image.new("RGB", (80, 120), (10, 10, 10))
    img.paste((240, 240, 240), (0, 0, 80, 60))
    return img


def test_gate_passes_on_animated_nonblank(tmp_path):
    plan = _plan_one_page(tmp_path)
    render = lambda site, f: {"frames": _frames(True), "settled": _nonblank(),
                              "n_animations": 3, "timestamps_ms": [0, 1, 2]}
    assert run_lean_gate(tmp_path, plan, render) == []


def test_gate_flags_no_animation_and_blank(tmp_path):
    plan = _plan_one_page(tmp_path)
    blank = Image.new("RGB", (80, 120), (10, 10, 10))
    render = lambda site, f: {"frames": _frames(False), "settled": blank,
                              "n_animations": 0, "timestamps_ms": [0, 1, 2]}
    checks = {d["check"] for d in run_lean_gate(tmp_path, plan, render)}
    assert "animates" in checks and "renders" in checks


def test_gate_flags_script(tmp_path):
    plan = _plan_one_page(tmp_path)
    (tmp_path / "index.html").write_text("<html><body><script>x()</script></body></html>")
    render = lambda site, f: {"frames": _frames(True), "settled": _frames(True)[1],
                              "n_animations": 2, "timestamps_ms": [0, 1, 2]}
    assert any(d["check"] == "no_js" for d in run_lean_gate(tmp_path, plan, render))


# ---- eval toml flip --------------------------------------------------------

def test_flip_agent_internet_flips_only_agent_env():
    toml = ('[environment]\nallow_internet = false\ncpus = 2\n\n'
            '[verifier.environment]\nallow_internet = true\ncpus = 2\n')
    out = _flip_agent_internet(toml)
    # agent flipped to true; verifier still true (unchanged); no false remains
    assert out.count("allow_internet = true") == 2
    assert "allow_internet = false" not in out


# ---- curate ----------------------------------------------------------------

def _make_survivor(batch, sid, archetype, aesthetic):
    d = batch / sid
    (d / "site").mkdir(parents=True)
    (d / "task").mkdir(parents=True)
    (d / "task" / "task.toml").write_text("[task]\nname='x'\n")
    (d / "site" / "seed.json").write_text(json.dumps(
        {"seed_tuple": [archetype, aesthetic, "low", "aud", "mood", "smooth-fade"]}))


def test_curate_dedupes_by_cell_and_keeps_whole_seed_dir(tmp_path):
    batch = tmp_path / "batch"
    _make_survivor(batch, "000_saas_swiss", "saas", "swiss")
    _make_survivor(batch, "001_saas_swiss", "saas", "swiss")   # dup cell -> dropped
    _make_survivor(batch, "002_blog_flat", "blog", "flat")
    kept = curate(batch, tmp_path / "out")
    assert kept == ["000_saas_swiss", "002_blog_flat"]
    # whole seed dir copied (Task-1 parity): BOTH task/ and site/ kept
    assert (tmp_path / "out" / "000_saas_swiss" / "task" / "task.toml").exists()
    assert (tmp_path / "out" / "000_saas_swiss" / "site" / "seed.json").exists()


def test_task_dirs_resolves_curated_task_subdir(tmp_path):
    from webdesign_rl_anim.evaluate_anim import _job_name, _task_dirs
    cur = tmp_path / "curated"
    for sid in ["000_a_b", "001_c_d"]:
        (cur / sid / "task").mkdir(parents=True)
        (cur / sid / "task" / "task.toml").write_text("x")
        (cur / sid / "site").mkdir()
    dirs = _task_dirs(cur)
    assert [d.name for d in dirs] == ["task", "task"]            # the runnable task dir
    assert [_job_name(d) for d in dirs] == ["000_a_b", "001_c_d"]  # seed-id job names


# ---- prefill-free continuation (the robustness fix) ------------------------

class _Blk:
    type = "text"
    def __init__(self, text): self.text = text

class _Msg:
    def __init__(self, text, stop): self.content = [_Blk(text)]; self.stop_reason = stop

def _continuing_client(canned_msgs):
    from webdesign_rl_anim.gen_client import ContinuingGenerationClient
    c = ContinuingGenerationClient.__new__(ContinuingGenerationClient)  # no API init
    c._model, c._max_tokens, c._max_continuations = "m", 100, 4
    c._canned, c._seen = list(canned_msgs), []
    def _create(**kwargs):
        c._seen.append(kwargs["messages"])
        return c._canned.pop(0)
    c._create_with_retry = _create
    return c

def test_continuation_stitches_and_ends_on_user_turn():
    # First response truncates; second completes.
    c = _continuing_client([_Msg("AAA", "max_tokens"), _Msg("BBB", "end_turn")])
    out = c.complete("prompt", temperature=0.7)
    assert out == "AAABBB"
    # the continuation request ends with a USER message (NOT prefill)
    assert c._seen[1][-1]["role"] == "user"
    assert c._seen[1][-2]["role"] == "assistant"  # partial carried as context

def test_continuation_trims_repeated_seam():
    # Continuation re-emits the tail ("AAA"); overlap is trimmed, not duplicated.
    c = _continuing_client([_Msg("hello AAA", "max_tokens"), _Msg("AAA world", "end_turn")])
    assert c.complete("p", temperature=0.6) == "hello AAA world"

def test_continuation_raises_when_never_completes():
    import pytest
    c = _continuing_client([_Msg("x", "max_tokens")] * 10)  # always truncated
    with pytest.raises(ValueError):
        c.complete("p", temperature=0.6)
