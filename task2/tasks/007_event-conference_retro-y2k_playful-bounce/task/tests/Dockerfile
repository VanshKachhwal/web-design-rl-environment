FROM python:3.14-slim

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

# Browser engine first (large, source-independent layer).
RUN pip install --no-cache-dir "playwright>=1.49" \
    && playwright install --with-deps chromium

# Task 1 package (reused static metrics + judge) with the grade extra.
COPY webdesign_rl_pkg /opt/webdesign_rl_pkg
RUN pip install --no-cache-dir /opt/webdesign_rl_pkg[grade]
ENV WEBDESIGN_RL_PKG_ROOT=/opt/webdesign_rl_pkg

# Task 2 animation package, on PYTHONPATH (pure-python; deps satisfied above).
COPY webdesign_rl_anim_pkg /opt/webdesign_rl_anim_pkg
ENV PYTHONPATH=/opt/webdesign_rl_anim_pkg

# Baked, hidden-from-agent grader inputs.
COPY reference_site /tests/reference_site
COPY page_map.json /tests/page_map.json

COPY test.sh /tests/test.sh
RUN chmod +x /tests/test.sh
