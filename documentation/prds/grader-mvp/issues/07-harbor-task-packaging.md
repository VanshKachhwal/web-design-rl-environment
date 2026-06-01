# 07 — Harbor task packaging (`emit`, separate verifier env)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

Package a reference site into a runnable Harbor task so the grader produces `reward.json`
inside a real trial. The `emit` step assembles: an `instruction.md` listing each screenshot,
its required output filename, and the render viewport; a `task.toml` configured for a
**separate verifier environment**; a verifier image carrying the renderer + Tesseract +
bundled fonts + grader code (hidden from the agent); and the agent-output→verifier transfer
via Harbor's `artifacts` field. Running the **oracle** agent (which emits the ground-truth
site) should score ≈ 1.0, confirming the packaged grader's ceiling end-to-end.

## Acceptance criteria

- [ ] `emit` produces a complete Harbor task directory (instruction, `task.toml`, environment, verifier) from a reference site + `page_map`.
- [ ] `instruction.md` states the screenshot→filename mapping and the viewport width.
- [ ] `task.toml` uses a separate verifier environment; grading code is not present in the agent environment.
- [ ] Agent output reaches the verifier via the `artifacts` mechanism.
- [ ] `harbor run -a oracle` on the packaged task yields reward ≈ 1.0.

## Blocked by

- Issue 05 (live render). Ideally also Issue 06 (validated grader) before relying on the scores.

## Comments

- **Done (2026-05-30), TDD.** 76 tests pass + 1 skipped (was 59). New: `tests/test_emit.py`
  (14) + `tests/test_grade_cli.py` (3). One emit test (`harbor`-schema round-trip) skips
  unless the `harbor` package is importable (it is a separate CLI tool, not a project dep);
  validated manually against Harbor's own `TaskConfig` schema instead.
- **`emit.build_task(reference_site_dir, page_map, out_task_dir, *, task_name, viewport,
  cpus, memory_mb)`** assembles a Harbor task: `instruction.md` (screenshot→output-file
  table + 1280px viewport + the `/logs/artifacts/` publish path), `task.toml` (separate
  `[verifier.environment]`, `environment_mode="separate"`, pinned `cpus`/`memory_mb`,
  verifier `allow_internet=true` + agent `allow_internet=false`, `[verifier.env]
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"`), minimal agent `environment/Dockerfile`,
  `solution/solve.sh` (oracle copies the bundled reference site → `/logs/artifacts/`), and
  `tests/` = the **verifier build context** (self-contained Dockerfile baking
  python+our package+playwright+`playwright install chromium`+tesseract+DejaVu fonts+grader+
  reference HTML+`page_map`, providing its own `/tests/test.sh`).
- **Agent→verifier transfer:** the agent publishes its site to `/logs/artifacts/` (Harbor's
  auto-transferred convention dir); for a separate verifier Harbor downloads it and re-uploads
  to the verifier's `/logs/artifacts/` — no `artifacts=` list needed. Confirmed in Harbor
  source (`single_step.py`/`trial.py`): verifier build context is `tests/`, `tests/` is NOT
  uploaded at runtime, image must ship `/tests/test.sh`.
- **Grader entrypoint:** `python -m webdesign_rl.grade --candidate --reference|--reference-site
  --page-map --out [--no-judge]`. `--no-judge` = deterministic-only (drops `design_judge`,
  reward = mean of structure/color/content; no key/egress) — threaded via `judge_client=None`
  through `grade()`/`aggregate(dimensions=...)`, existing 4-term behavior unchanged.
  `--reference-site` renders the reference HTML in-process so candidate+reference share
  engine/fonts (host-independent exact ceiling); `test.sh` uses it.
- **Layer B (live):** `harbor run -p <task> -a oracle -e docker --force-build` →
  **reward.json = {structure:1.0, color:1.0, content:1.0, reward:1.0}**. Two images built
  (agent 139MB vs verifier 2.89GB); verified the agent image has NO grader code / reference /
  python — grading fully hidden. (Initial run with committed host-rendered PNGs scored
  structure 0.91 from a macOS-Arial vs container-DejaVu font mismatch; switching the reference
  to in-container HTML render fixed the ceiling to exactly 1.0 and made it deterministic.)
- **Modal-portable:** plain Dockerfile only (no compose), self-contained image, pinned
  resources, verifier-only egress + key. Same task runs `--env docker` / `--env modal`
  unchanged. (Live Modal run not exercised here — no Modal creds in this env.)
