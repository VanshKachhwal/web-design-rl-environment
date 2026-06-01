# Replicate the web design

You are given reference **screenshots** of a 7-page website. Recreate
each page as faithfully as possible using **plain HTML and CSS**, matching the
layout, colors, typography, and text content you see in each screenshot.

You only have the screenshots — there is no reference source to copy. The reference
screenshots are PNG files in **`/app/reference/`**; open them to see what to
build. Your work is graded on how closely your *rendered* pages match these
reference screenshots.

## Rendering

Your pages are rendered headlessly at a fixed **viewport width of 1280px**
(full scroll height), offline. Use local/inline assets and CSS; external network
requests are blocked during rendering, so do not rely on CDNs or web fonts.

## Pages to produce

Write each output file listed below. The grader renders the file named in the
right column and compares it to the screenshot in the left column.

| Reference screenshot | Output file |
| --- | --- |
| `/app/reference/index.png` | `index.html` |
| `/app/reference/schedule.png` | `schedule.html` |
| `/app/reference/speakers.png` | `speakers.html` |
| `/app/reference/tickets.png` | `tickets.html` |
| `/app/reference/venue.png` | `venue.html` |
| `/app/reference/sponsors.png` | `sponsors.html` |
| `/app/reference/contact.png` | `contact.html` |

## Where to write your files

Write all of your HTML/CSS/asset files into **`/logs/artifacts/`** (create it if
needed). Keep every page's relative asset paths working from that directory. Only
files under `/logs/artifacts/` are collected and graded.
