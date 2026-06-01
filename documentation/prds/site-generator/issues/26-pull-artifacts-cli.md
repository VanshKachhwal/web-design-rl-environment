# 26 — pull_artifacts CLI: download a Modal volume to a local dir

Status: done

## Parent

PRD: `.scratch/site-generator/PRD.md`. New script replacing the manual
`modal volume get` step documented in `docs/modal_batch.md`. Sibling: issue 25
(`generate`). Grill-resolved this session.

## What to build

A CLI that downloads the generated artifacts off a Modal volume into a local
directory — the command form of the documented
`modal volume get webdesign-rl-artifacts / ./out/batch/`. It pulls **everything**
(every `<seed_id>/{site,task}` dir, including gate drops that have only `site/`),
faithfully mirroring the volume; survivor filtering happens downstream in
`curate` (`curate.survivors` keys on a `task/task.toml`).

**Pure core (unit-tested) — an argv builder (mirror `run_claude_code.build_harbor_argv`):**
- `build_pull_argv(volume, dest, *, force=False, env=None)` →
  `["modal", "volume", "get", volume, "/", str(dest)]`, appending `"--force"` when
  `force`, and `["-e", env]` (or `--env`) when an env is given. Pure, deterministic,
  no I/O — the tested seam.

**Thin shell (`scripts/pull_artifacts.py`) — untested:**
- argparse CLI:
  - `--volume NAME` (default `webdesign-rl-artifacts` — reuse `modal_batch.VOLUME_NAME`).
  - `--out DIR` (default **`out/<volume>`** — so `--volume batch-a` →
    `out/batch-a`; an explicit `--out` overrides).
  - `--force` (overwrite existing files; maps to `modal volume get --force`,
    default off — mirrors Modal's own default).
  - `-e/--env NAME` (Modal environment pass-through; default unset → workspace
    default).
- Builds the argv via `build_pull_argv(...)`, ensures `--out` exists, and
  `subprocess.run(argv, check=True)`. Prints the destination on success. The
  `subprocess` call is the untested shell (`# pragma: no cover`).
- Resulting layout is **curate-compatible**: `out/<volume>/<seed_id>/{site,task}`,
  exactly what `curate --batch out/<volume>` expects.

**Auth assumption:** pull relies on **Modal token auth only** (`modal token new`) —
no Anthropic key, no Secret, no `.env`. Flexible credential sourcing is tracked in
`docs/improvements.md` (out of scope here).

## Acceptance criteria

- [x] `pull_artifacts.py --volume V` downloads the whole volume to `out/V/` (default)
      via `modal volume get V / out/V`; `--out DIR` overrides the destination.
      (argv shape + `out/<volume>` default unit-asserted; live download is the
      untested `subprocess`/`modal` shell.)
- [x] `--force` adds `--force` to the modal command; omitted by default.
- [x] `-e/--env` passes the Modal environment through when given; omitted otherwise.
- [ ] The downloaded layout is `out/<volume>/<seed_id>/{site,task}` (drops included),
      consumable by `curate --batch out/<volume>` with no extra massaging.
      (Needs a live Modal pull to verify on-disk; the dest is `out/<volume>` so the
      layout mirrors the volume by construction.)
- [x] `build_pull_argv` is pure and **unit-tested**: correct argv for the
      default/`--force`/`--env`/custom-dest cases. The `subprocess`/`modal` call is
      the untested shell.
- [x] Script is import-safe without `modal`; `pull_artifacts.py --help` renders.
      Full suite green (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None. New `scripts/pull_artifacts.py` (+ the pure `build_pull_argv`, placed in the
  thin script or a small helper). Independent of issue 25 — they share only the
  volume-name convention, not code.
