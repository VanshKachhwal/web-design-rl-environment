# 05 — Live `render` module (HTML → deterministic screenshots)

Status: done

## Parent

PRD: `.scratch/grader-mvp/PRD.md`

## What to build

Replace the pre-rendered-PNG input path with a live renderer so the grader takes a candidate
**directory of HTML/CSS** and renders it itself. Serve the directory over a local HTTP server
(not `file://`, so relative assets and `@font-face` resolve), drive an offline headless
browser (internet disabled) with a **bundled local font set**, and capture a **full-page
screenshot at a fixed width (default 1280px)**. Rendering must be deterministic: the same
site renders to byte/hash-stable screenshots across runs.

The grader's `render → metrics → aggregate` flow now begins from source files for the
candidate; the reference may be supplied as screenshots or re-rendered the same way.

## Acceptance criteria

- [ ] `render_site(dir, page_map, viewport)` returns one full-page screenshot per page at the requested width.
- [ ] Rendering runs offline with bundled fonts; no network fetches at render time.
- [ ] Served over local HTTP; relative asset paths and `@font-face` load correctly.
- [ ] Rendering the same fixed site twice yields hash-stable screenshots.
- [ ] The grader accepts a candidate directory end-to-end and still produces `reward.json` + `reward-details.json`.
- [ ] Tests cover render determinism and output dimensions.

## Blocked by

- Issue 01 (walking skeleton + grader contract).

## Comments

- **Done (2026-05-30).** 41 tests pass. `render/browser.py::render_site(site_dir, page_map,
  viewport=1280)` serves the dir over an ephemeral-port local HTTP server and captures
  full-page Chromium screenshots. **Offline determinism:** route-intercept aborts every
  non-localhost request; deterministic flags (`--disable-gpu`, sRGB, device_scale_factor=1,
  reduced-motion). Determinism asserted as byte-identical OR zero pixel diff.
- **Grader integration:** `grade()` now calls `render_site(candidate_dir, ...)` once and
  compares rendered candidate vs committed reference PNG. `expected_file` now names the
  candidate **HTML** file. Reference unchanged. Grader tests migrated to HTML fixtures.
- `playwright` moved to core deps; the Chromium binary must be installed once
  (`playwright install chromium`).
- **For issue 07 (Harbor):** verifier image must `playwright install chromium` AND bundle a
  deterministic font set referenced via relative `@font-face` (currently relies on host
  fonts — fine locally, must be explicit in the container).
