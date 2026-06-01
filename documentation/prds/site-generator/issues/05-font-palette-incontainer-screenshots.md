# 05 — Font palette: OS-level install + in-container agent screenshots (supersedes issue 09)

Status: done (committed ac54fef)

## Parent

PRD: `.scratch/site-generator/PRD.md`

## What to build

Make typography faithful and deterministic by curating a font palette, installing it
**OS-level** in the render/verifier image, and rendering the agent's reference screenshots
**in-container** — which **supersedes** the `@font-face` patch planned in grader-mvp issue 09.

- **Fonts manifest** — one source of truth listing the palette: 8 OFL families (Inter, Work
  Sans, Space Grotesk, Archivo (+heavy/Anton), Playfair Display, Source Serif 4, Poppins,
  JetBrains Mono) + DejaVu fallback. Feeds three consumers: the image install, the generation
  allow-list, and the gate's hermeticity check.
- **OS-level install** — vendor pinned `.ttf` files into the repo, `COPY` them into
  `/usr/share/fonts` + `fc-cache` in the emit verifier image (replacing the DejaVu-only
  `apt` line as the palette). Sites reference fonts by **bare family name** (no `@font-face`),
  so the agent's `font-family: Inter` resolves in the verifier render — mandatory for
  well-posedness.
- **In-container agent screenshots** — render the agent-facing reference PNGs in the **same
  sealed image** as grading (not the host), eliminating host/container font drift (the
  issue-07/09 bug class) at the root.
- **Generation constraint** — stage 2 may only pick families from the manifest; display faces
  are **headings-only**.
- **Re-status grader-mvp issue 09** as superseded by this approach (do not build its
  `@font-face` patch).

## Acceptance criteria

- [ ] A fonts manifest exists and drives image install + generation allow-list + gate
      hermeticity check (no duplicated font lists).
- [ ] The verifier/render image installs the palette OS-level; a site using palette fonts by
      bare family name renders with the intended typography (not DejaVu fallback).
- [ ] Agent reference screenshots are rendered in-container; the oracle still scores ≈ 1.0
      (no host/container font mismatch).
- [ ] The gate fails a site using any `font-family` outside the palette.
- [ ] grader-mvp issue 09 is re-statused as superseded with a pointer to this slice.

## Blocked by

- 01 (needs generated sites + the render path to install the palette into and constrain).
