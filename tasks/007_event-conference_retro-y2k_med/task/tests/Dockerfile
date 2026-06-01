FROM python:3.14-slim

# System deps: Tesseract (content/OCR term) + the DejaVu fallback font set
# (every palette family degrades to it identically) + curl (build-time palette
# fetch), plus the libraries headless Chromium needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        fonts-dejavu-core \
        fontconfig \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

# The curated font palette (issue 05), installed OS-level so a site's
# `font-family: Inter` resolves by bare name rather than falling back to
# DejaVu. Pinned .ttf files are fetched from google/fonts at a fixed
# commit (fafaa09e4abf799c185f85e9b6eacb7db31ca5ed) during build (build-time has
# network; the render at grade time stays offline), then fc-cache'd.
RUN mkdir -p /usr/share/fonts/truetype/webdesign-palette \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/Inter[opsz,wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/inter/Inter[opsz,wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/WorkSans[wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/worksans/WorkSans[wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/SpaceGrotesk[wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/spacegrotesk/SpaceGrotesk[wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/Archivo[wdth,wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/archivo/Archivo[wdth,wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/Anton-Regular.ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/anton/Anton-Regular.ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/PlayfairDisplay[wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/playfairdisplay/PlayfairDisplay[wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/SourceSerif4[opsz,wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/sourceserif4/SourceSerif4[opsz,wght].ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/Poppins-Regular.ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/poppins/Poppins-Regular.ttf" \
    && curl -fsSL --globoff --retry 3 -o "/usr/share/fonts/truetype/webdesign-palette/JetBrainsMono[wght].ttf" "https://raw.githubusercontent.com/google/fonts/fafaa09e4abf799c185f85e9b6eacb7db31ca5ed/ofl/jetbrainsmono/JetBrainsMono[wght].ttf" \
    && fc-cache -f

# Browser-engine layer FIRST, before the package + per-task COPYs. Chromium and
# its OS deps (--with-deps) are large and source-INDEPENDENT, so placing them
# ahead of the COPYs means a package or per-task change busts only the cheap
# layers below rather than re-baking Chromium. playwright is a core dep
# (>=1.49), so installing it here leaves it satisfied by the package install
# below — the engine matches this baked Chromium (no version/binary drift).
RUN pip install --no-cache-dir "playwright>=1.49" \
    && playwright install --with-deps chromium

# Our package + its dependencies (Playwright is a core dep as of issue 05).
COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]

# Where task_builder re-stages the package from when emitting inside an image
# (parity with the render image; harmless here since the verifier never emits).
ENV WEBDESIGN_RL_PKG_ROOT=/opt/webdesign_rl_pkg

# Bake the grader inputs hidden from the agent: the reference HTML site (rendered
# in-container at grade time with the same engine/fonts as the candidate, so the
# ceiling is exact and host-independent) + page_map.
COPY reference_site /tests/reference_site
COPY page_map.json /tests/page_map.json

# The verifier entrypoint. For a separate verifier env Harbor does NOT upload
# tests/, so the image must provide /tests/test.sh itself.
COPY test.sh /tests/test.sh
RUN chmod +x /tests/test.sh
