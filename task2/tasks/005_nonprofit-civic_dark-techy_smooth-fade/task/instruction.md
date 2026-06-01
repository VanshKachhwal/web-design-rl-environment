# Replicate the animated web design

You are given a reference **animated** 5-page website as *filmstrips*:
for each page, full-page screenshots captured at increasing times after load
(0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms), plus a single stacked **contact sheet** and the final at-rest frame.
Recreate every page using **plain HTML and CSS only**, matching both the **static
design** (layout, colors, typography, text) *and* the **animation** (what moves,
when, the easing/feel, and the kind of motion). Reuse one shared stylesheet across
pages for consistency.

## Reference (one filmstrip per page)

### `index.html`

- Filmstrip frames: `/app/reference/index_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/index_filmstrip.png`
- Final at-rest frame: `/app/reference/index_settled.png`

### `platform-features.html`

- Filmstrip frames: `/app/reference/platform-features_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/platform-features_filmstrip.png`
- Final at-rest frame: `/app/reference/platform-features_settled.png`

### `data-insights.html`

- Filmstrip frames: `/app/reference/data-insights_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/data-insights_filmstrip.png`
- Final at-rest frame: `/app/reference/data-insights_settled.png`

### `community-partners.html`

- Filmstrip frames: `/app/reference/community-partners_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/community-partners_filmstrip.png`
- Final at-rest frame: `/app/reference/community-partners_settled.png`

### `get-started.html`

- Filmstrip frames: `/app/reference/get-started_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/get-started_filmstrip.png`
- Final at-rest frame: `/app/reference/get-started_settled.png`

Your pages are captured at the **same absolute times** and graded on how closely
each frame — and the motion between them — matches.

## Animation rules (important)

- Use **CSS only**: `@keyframes` animations and CSS transitions. **No JavaScript**,
  no `<script>`, no `requestAnimationFrame` — the grader seeks the CSS timeline and
  will not see JS-driven motion.
- Give finite entrance/stagger animations `animation-fill-mode: forwards` so each
  page holds its final state at rest (the settled frame is graded for static design).
- Match the **timing**: entrance + stagger should play within the same window you
  see in the filmstrip; reproduce any continuous (infinite) loops you observe.

## Rendering

Rendered headlessly at a fixed **viewport width of 1280px** (full scroll
height), **offline** — use local/inline CSS, system fonts, CSS-drawn shapes/
gradients; no CDNs or web fonts.

## Pages to produce

| Reference contact sheet | Output file |
| --- | --- |
| `index_filmstrip.png` | `index.html` |
| `platform-features_filmstrip.png` | `platform-features.html` |
| `data-insights_filmstrip.png` | `data-insights.html` |
| `community-partners_filmstrip.png` | `community-partners.html` |
| `get-started_filmstrip.png` | `get-started.html` |

## Where to write your files

Write all your HTML/CSS files into **`/logs/artifacts/`** (create it if needed),
keeping relative asset paths working from there. Only files under `/logs/artifacts/`
are collected and graded.
