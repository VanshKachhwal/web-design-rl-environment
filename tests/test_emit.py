"""Layer A tests for ``emit.build_task`` — the Harbor task packager.

These are fast, Docker-free, deterministic file/content assertions: given a
reference site directory and a ``page_map``, ``build_task`` must assemble a
*complete, valid* Harbor task directory wired for a **separate verifier
environment**. We assert the externally-observable contract of that directory —
which files exist, what the ``task.toml`` declares, what ``instruction.md`` tells
the agent — not how the builder wrote them.

The integration (Layer B) check that ``harbor run -a oracle`` actually scores
~1.0 is separate and Docker-gated.
"""

import tomllib
from pathlib import Path

import pytest

from webdesign_rl.emit import build_task

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE_SITE = FIXTURES / "site5_reference"

PAGE_MAP = {
    "home": {"screenshot": "home.png", "expected_file": "index.html"},
    "about": {"screenshot": "about.png", "expected_file": "about.html"},
    "services": {"screenshot": "services.png", "expected_file": "services.html"},
    "pricing": {"screenshot": "pricing.png", "expected_file": "pricing.html"},
    "contact": {"screenshot": "contact.png", "expected_file": "contact.html"},
}


def _fast_render(site_dir, page_map, viewport=1280):
    """An in-process stand-in for the default in-container render.

    These tests assert the *packaging structure* build_task produces, not font
    fidelity, so they inject a fast renderer to avoid a Docker build. The
    in-container default (the actual issue-05 behavior) is covered separately by
    the injected-render unit test + the Docker-gated container render test.
    """
    from PIL import Image

    return {name: Image.new("RGB", (viewport, 700), (90, 90, 90))
            for name in page_map}


@pytest.fixture(scope="module")
def task_dir(tmp_path_factory):
    """Build the task once for the whole module (rendering is the slow part)."""
    out = tmp_path_factory.mktemp("task")
    build_task(REFERENCE_SITE, PAGE_MAP, out, render=_fast_render)
    return out


def test_build_task_produces_core_harbor_files(task_dir):
    # The canonical Harbor task skeleton: instruction, config, agent env,
    # oracle solution, and the verifier build context (tests/).
    assert (task_dir / "instruction.md").is_file()
    assert (task_dir / "task.toml").is_file()
    assert (task_dir / "environment" / "Dockerfile").is_file()
    assert (task_dir / "solution" / "solve.sh").is_file()
    assert (task_dir / "tests" / "Dockerfile").is_file()
    assert (task_dir / "tests" / "test.sh").is_file()


def _toml(task_dir):
    return tomllib.loads((task_dir / "task.toml").read_text())


def test_task_toml_declares_separate_verifier_env(task_dir):
    cfg = _toml(task_dir)
    # A separate verifier env hides the grading code from the agent.
    assert cfg["verifier"]["environment_mode"] == "separate"
    assert "environment" in cfg["verifier"]


def test_task_toml_pins_verifier_resources(task_dir):
    # Cloud backends enforce these, so they must be explicit integers.
    env = _toml(task_dir)["verifier"]["environment"]
    assert isinstance(env["cpus"], int) and env["cpus"] >= 1
    assert isinstance(env["memory_mb"], int) and env["memory_mb"] >= 1024


def test_task_toml_verifier_allows_internet_for_judge(task_dir):
    # The design_judge term needs egress to the Anthropic API; the agent env does
    # not (rendering is offline), so only the verifier opts in.
    cfg = _toml(task_dir)
    assert cfg["verifier"]["environment"]["allow_internet"] is True
    assert cfg["environment"]["allow_internet"] is False


def test_task_toml_passes_api_key_to_verifier(task_dir):
    # The key is templated from the host env so it is never committed.
    verifier_env = _toml(task_dir)["verifier"]["env"]
    assert verifier_env["ANTHROPIC_API_KEY"] == "${ANTHROPIC_API_KEY}"


def test_task_toml_parses_as_valid_harbor_config(task_dir):
    # The emitted config must round-trip through Harbor's own schema, proving the
    # separate-verifier wiring is well-formed (not just our reading of it). Harbor
    # is a separate CLI tool, not a project dependency, so skip if unavailable —
    # Layer B re-checks this with the real `harbor` CLI.
    config = pytest.importorskip("harbor.models.task.config")
    verifier_mode = pytest.importorskip("harbor.models.task.verifier_mode")

    cfg = config.TaskConfig.model_validate_toml(
        (task_dir / "task.toml").read_text()
    )
    assert (
        verifier_mode.resolve_task_verifier_mode(cfg)
        == config.VerifierEnvironmentMode.SEPARATE
    )


def test_instruction_lists_screenshot_to_output_filename(task_dir):
    text = (task_dir / "instruction.md").read_text()
    # Every page's reference screenshot and its required output filename must be
    # stated so the agent knows what to produce and how it is graded.
    for spec in PAGE_MAP.values():
        assert spec["screenshot"] in text
        assert spec["expected_file"] in text


def test_agent_screenshots_use_the_injected_render(tmp_path):
    # Issue 05: the agent reference PNGs must be rendered in the SAME sealed
    # image/font environment as grading, not on the host. build_task therefore
    # takes the renderer as a seam (default = the sealed in-container render);
    # injecting a render proves the screenshots come from whatever environment
    # the caller designates, and lets the fast suite avoid a Docker build.
    from PIL import Image

    calls = {}

    def fake_render(site_dir, page_map, viewport=1280):
        calls["site_dir"] = Path(site_dir)
        calls["viewport"] = viewport
        red = Image.new("RGB", (viewport, 700), (200, 10, 10))
        return {name: red for name in page_map}

    out = tmp_path / "task"
    build_task(REFERENCE_SITE, PAGE_MAP, out, render=fake_render)

    # The injected renderer was actually used (its red PNGs are on disk).
    assert calls["site_dir"] == REFERENCE_SITE
    ref_dir = out / "environment" / "reference"
    for spec in PAGE_MAP.values():
        png = ref_dir / spec["screenshot"]
        assert png.is_file()
        assert Image.open(png).getpixel((0, 0)) == (200, 10, 10)


def test_agent_env_contains_reference_screenshots(task_dir):
    # The whole point of issue 08: the agent must actually be given the reference
    # screenshots. One PNG per page is rendered into the agent-env build context.
    ref_dir = task_dir / "environment" / "reference"
    for spec in PAGE_MAP.values():
        png = ref_dir / spec["screenshot"]
        assert png.is_file()
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG, not empty


def test_agent_dockerfile_copies_reference_screenshots(task_dir):
    # The agent container must actually receive the screenshots: environment/ is
    # the build context, so the Dockerfile COPYs reference/ into /app/reference.
    df = (task_dir / "environment" / "Dockerfile").read_text()
    assert "COPY reference /app/reference" in df


def test_instruction_points_agent_at_screenshot_paths(task_dir):
    # instruction.md must reference the in-container paths the agent can open, not
    # just bare filenames.
    text = (task_dir / "instruction.md").read_text()
    assert "/app/reference" in text
    for spec in PAGE_MAP.values():
        assert f"/app/reference/{spec['screenshot']}" in text


def test_instruction_states_render_viewport(task_dir):
    # The agent must know the fixed capture width to lay out its design.
    assert "1280px" in (task_dir / "instruction.md").read_text()


def test_instruction_tells_agent_where_to_publish(task_dir):
    # The screenshots-only contract + the publish path that reaches the verifier.
    text = (task_dir / "instruction.md").read_text()
    assert "/logs/artifacts" in text


def test_reference_site_and_page_map_baked_into_verifier(task_dir):
    # The verifier image carries the (hidden) reference HTML site + page_map. The
    # reference is the HTML, not committed PNGs, so the verifier renders it with
    # the SAME engine/fonts as the candidate -> a host-independent exact ceiling.
    import json as _json

    ref_site = task_dir / "tests" / "reference_site"
    for spec in PAGE_MAP.values():
        assert (ref_site / spec["expected_file"]).is_file()
    baked = _json.loads((task_dir / "tests" / "page_map.json").read_text())
    assert baked == PAGE_MAP


def test_grader_code_baked_into_verifier_context(task_dir):
    # The grader travels with the task (self-contained image), not via a registry.
    pkg = task_dir / "tests" / "webdesign_rl_pkg"
    assert (pkg / "pyproject.toml").is_file()
    assert (pkg / "src" / "webdesign_rl" / "grade" / "__main__.py").is_file()
    assert (pkg / "src" / "webdesign_rl" / "grade" / "grader.py").is_file()


def test_solution_reproduces_the_reference_pages(task_dir):
    # The oracle bundles the ground-truth HTML and solve.sh publishes it, so the
    # oracle's output is the reference site -> grader ceiling ~1.0.
    solve = (task_dir / "solution" / "solve.sh").read_text()
    assert "/logs/artifacts" in solve
    site = task_dir / "solution" / "site"
    for spec in PAGE_MAP.values():
        assert (site / spec["expected_file"]).is_file()


def test_verifier_image_is_self_contained(task_dir):
    # Modal-portability: a plain Dockerfile that bakes in everything the grader
    # needs (no host paths, no runtime downloads of chromium/fonts/tesseract).
    df = (task_dir / "tests" / "Dockerfile").read_text()
    assert "tesseract-ocr" in df              # OCR (content term)
    assert "fonts-" in df                      # bundled deterministic font set
    assert "playwright install" in df          # chromium binary baked in
    assert "chromium" in df
    assert "/tests/test.sh" in df              # the image provides its own test.sh
    assert "reference_site" in df              # the reference HTML is baked in


def test_verifier_image_installs_the_font_palette_os_level(task_dir):
    # Issue 05: the verifier/render image installs the curated palette OS-level so
    # a site's `font-family: Inter` resolves by bare name (not DejaVu fallback).
    # The .ttf files are fetched at build time from google/fonts pinned to a SHA,
    # dropped into /usr/share/fonts, then fc-cache'd. DejaVu stays as fallback.
    from webdesign_rl.generate import fonts

    df = (task_dir / "tests" / "Dockerfile").read_text()
    # Pinned to a specific commit SHA (reproducible), fetched at build time.
    assert fonts.PINNED_FONTS_SHA in df
    # Every palette family's pinned .ttf URL is fetched.
    for url in fonts.install_urls():
        assert url in df
    # Installed where fontconfig sees them, then the cache is refreshed.
    assert "/usr/share/fonts" in df
    assert "fc-cache" in df
    # DejaVu remains the deterministic fallback.
    assert "fonts-dejavu-core" in df


def test_verifier_test_sh_runs_deterministic_grader(task_dir):
    # test.sh invokes the grader CLI in deterministic-only mode against the agent's
    # published artifacts and writes the reward into /logs/verifier.
    sh = (task_dir / "tests" / "test.sh").read_text()
    assert "python -m webdesign_rl.grade" in sh
    assert "--candidate /logs/artifacts" in sh
    assert "--reference-site /tests/reference_site" in sh
    assert "--no-judge" in sh
    assert "/logs/verifier" in sh


def test_no_compose_file_emitted(task_dir):
    # Cloud sandboxes only support a plain Dockerfile env, never docker-compose.
    assert not (task_dir / "environment" / "docker-compose.yaml").exists()
    assert not (task_dir / "tests" / "docker-compose.yaml").exists()
