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

### `work.html`

- Filmstrip frames: `/app/reference/work_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/work_filmstrip.png`
- Final at-rest frame: `/app/reference/work_settled.png`

### `services.html`

- Filmstrip frames: `/app/reference/services_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/services_filmstrip.png`
- Final at-rest frame: `/app/reference/services_settled.png`

### `about.html`

- Filmstrip frames: `/app/reference/about_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/about_filmstrip.png`
- Final at-rest frame: `/app/reference/about_settled.png`

### `contact.html`

- Filmstrip frames: `/app/reference/contact_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/contact_filmstrip.png`
- Final at-rest frame: `/app/reference/contact_settled.png`

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
| `work_filmstrip.png` | `work.html` |
| `services_filmstrip.png` | `services.html` |
| `about_filmstrip.png` | `about.html` |
| `contact_filmstrip.png` | `contact.html` |

## Where to write your files

Write all your HTML/CSS files into **`/logs/artifacts/`** (create it if needed),
keeping relative asset paths working from there. Only files under `/logs/artifacts/`
are collected and graded.
