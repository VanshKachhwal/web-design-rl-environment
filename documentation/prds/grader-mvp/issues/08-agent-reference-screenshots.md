# 08 — Place reference screenshots in the agent environment

Status: ready-for-agent

## Parent

PRD: `.scratch/grader-mvp/PRD.md` (follow-up bug found reviewing issue 07)

## Scope note

This was originally one issue covering both *placing the screenshots* and *font
consistency*. It is now split: **this issue (08)** only makes `emit` render the
reference screenshots and put them where the agent can see them. The font-mismatch
fix (bundling DejaVu via `@font-face` so host-rendered agent screenshots match the
in-container grading render) is split out to **issue 09** and is intentionally
*not* done here.

## What to build

The emitted task tells the agent "you are given reference screenshots `home.png`…"
but those PNGs are **not placed anywhere the agent can see** — only the oracle
(which copies the ground-truth site and ignores screenshots) works. A real agent
(Claude Code) has nothing to replicate. Fix `emit` to **render one reference
screenshot per page and place them in the agent environment** at a documented
path, and point `instruction.md` at those paths.

## Acceptance criteria

- [ ] `emit.build_task(...)` renders one reference screenshot per page (via
  `render_site`) and writes them into the **agent environment build context**
  (`environment/reference/<screenshot>.png`).
- [ ] `environment/Dockerfile` copies them into the agent container at a documented
  path (`/app/reference/`); verify the agent-env build context against the Harbor
  task-structure docs (the `environment/` dir is the agent image build context).
- [ ] `instruction.md` points the agent at the actual screenshot file paths it can
  open (e.g. `/app/reference/home.png`).
- [ ] Tests: emit produces the per-page screenshots, places them in the agent-env
  build context, and references their in-container paths in `instruction.md`;
  existing 76 tests stay green.

## Notes

- Rendering happens on the **host** at emit time. Until issue 09 bundles a font via
  `@font-face`, the host render (macOS fonts) can differ from the in-container
  grading render (DejaVu) → minor layout/glyph drift. That is a *known, deferred*
  limitation tracked in issue 09; it does not block giving the agent something to
  look at, which is the whole point of this issue.
- Keep grading on `--reference-site` (in-container render = same rasteriser as the
  candidate). The agent-facing screenshots are a separate artifact for the agent to
  view.

## Blocked by

- Issue 07 (Harbor packaging). Done.
