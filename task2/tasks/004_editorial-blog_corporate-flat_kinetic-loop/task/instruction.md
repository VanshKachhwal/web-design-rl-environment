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

### `articles-browse-all.html`

- Filmstrip frames: `/app/reference/articles-browse-all_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/articles-browse-all_filmstrip.png`
- Final at-rest frame: `/app/reference/articles-browse-all_settled.png`

### `about-our-mission.html`

- Filmstrip frames: `/app/reference/about-our-mission_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/about-our-mission_filmstrip.png`
- Final at-rest frame: `/app/reference/about-our-mission_settled.png`

### `resources-for-educators.html`

- Filmstrip frames: `/app/reference/resources-for-educators_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/resources-for-educators_filmstrip.png`
- Final at-rest frame: `/app/reference/resources-for-educators_settled.png`

### `contact-get-in-touch.html`

- Filmstrip frames: `/app/reference/contact-get-in-touch_t<ms>.png` (at 0 ms, 200 ms, 500 ms, 900 ms, 1400 ms, 2000 ms)
- Contact sheet (all frames stacked): `/app/reference/contact-get-in-touch_filmstrip.png`
- Final at-rest frame: `/app/reference/contact-get-in-touch_settled.png`

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
| `articles-browse-all_filmstrip.png` | `articles-browse-all.html` |
| `about-our-mission_filmstrip.png` | `about-our-mission.html` |
| `resources-for-educators_filmstrip.png` | `resources-for-educators.html` |
| `contact-get-in-touch_filmstrip.png` | `contact-get-in-touch.html` |

## Where to write your files

Write all your HTML/CSS files into **`/logs/artifacts/`** (create it if needed),
keeping relative asset paths working from there. Only files under `/logs/artifacts/`
are collected and graded.
