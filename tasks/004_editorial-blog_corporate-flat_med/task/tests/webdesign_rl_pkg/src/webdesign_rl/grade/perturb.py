"""Ordered programmatic degradations of a reference, for the monotonicity study.

The validation study (``scripts/validate_grader.py``) needs variants of a
reference whose *quality ordering is known a priori*, so it can check the grader's
reward respects that ordering. This module manufactures that ground truth.

Three families, each with the property the study depends on — **a higher severity
is a strictly worse replication on that perturbation's own axis**:

- **Image-space** (``f(img, severity) -> Image``): operate on a rendered reference
  PIL image and return a degraded image. ``color_drift``, ``gaussian_blur``,
  ``spatial_shift``, ``region_occlusion``, ``pixel_noise``. ``severity`` is a
  float in [0, 1]; 0.0 returns the reference essentially unchanged. These stress
  one grader metric each, cheaply, without re-rendering.
- **Source-space** (``f(site_dir, out_dir, severity) -> out_dir``): copy the
  reference HTML/CSS site, apply a controlled edit, and return the new directory
  for the study to re-render. ``remove_element``, ``swap_font``, ``shift_palette``,
  ``delete_text``. These add realism (a real DOM change), at the cost of a render.
- **Degenerate generators** (``f(size) -> Image``): return an image directly with
  no reference content — ``blank_page`` (white), ``solid_color``, ``lorem_ipsum``.
  They are the anti-gaming floor: outputs that share *some* trivial property with a
  page (it is an image; it has text) but replicate nothing, and so must score at
  the aggregate floor.

Image-space and degenerate functions are pure and deterministic (a fixed RNG seed
for noise), so the study and its Layer-A tests are network-free and reproducible.
"""

import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from skimage.color import lab2rgb, rgb2lab

# Severity is always a float in [0, 1]. Each perturbation maps 0 -> (near) the
# reference and 1 -> its worst controlled degradation, monotonically in between.

# --- Source-space perturbations ------------------------------------------------
#
# Each copies the reference site into ``out_dir`` and applies a controlled edit so
# the study can re-render it (a real DOM/CSS change, not a pixel hack). They return
# ``out_dir`` for chaining into ``render_site``.


def _copy_site(site_dir, out_dir) -> Path:
    """Copy a reference site directory to ``out_dir`` (fresh), returning the path."""
    site_dir, out_dir = Path(site_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(site_dir, out_dir)
    return out_dir


def delete_text(site_dir, out_dir, severity: float) -> Path:
    """Delete a growing fraction of the visible text from the HTML.

    The page's text nodes (between ``>`` and ``<``) are split into words; the
    trailing ``severity`` fraction of them is removed, so OCR finds fewer of the
    reference's words as severity grows. Severity 0 leaves the text intact.
    """
    out = _copy_site(site_dir, out_dir)
    index = out / "index.html"
    html = index.read_text()

    def thin(match):
        words = match.group(0).split()
        if not words:
            return match.group(0)
        keep = max(0, round(len(words) * (1.0 - severity)))
        return " " + " ".join(words[:keep]) + " " if keep else " "

    # Text between a closing ``>`` and the next opening ``<`` is visible content.
    new_html = re.sub(r"(?<=>)([^<>]+)(?=<)", thin, html)
    index.write_text(new_html)
    return out


def remove_element(site_dir, out_dir, severity: float) -> Path:
    """Remove whole ``<section>`` blocks from the page as severity grows.

    Dropping a section removes layout *and* its text — a realistic "missing
    content" failure. Severity 0 removes nothing; higher severity removes more of
    the page's sections (last-first, so the header survives longest).
    """
    out = _copy_site(site_dir, out_dir)
    index = out / "index.html"
    html = index.read_text()
    sections = list(re.finditer(r"<section\b.*?</section>", html, flags=re.S))
    n_remove = int(round(len(sections) * severity))
    # Remove the trailing ``n_remove`` sections (highest index first so spans stay
    # valid as we splice the string).
    for match in reversed(sections[len(sections) - n_remove:]):
        html = html[: match.start()] + html[match.end():]
    index.write_text(html)
    return out


# Replacement font stack, deliberately a different family from the reference's
# sans-serif so the typography visibly changes when rendered.
_SWAP_FONT = '"Times New Roman", Georgia, serif'


def swap_font(site_dir, out_dir, severity: float) -> Path:
    """Swap the body font to a contrasting family (serif) when severity > 0.

    Typography is a step change, not a smooth axis, so this is binary: severity 0
    keeps the reference font; any positive severity swaps it. Used as a single
    realism point rather than a graded ladder.
    """
    out = _copy_site(site_dir, out_dir)
    css_path = out / "style.css"
    css = css_path.read_text()
    if severity > 0:
        css = re.sub(
            r"font-family:[^;]+;",
            f"font-family: {_SWAP_FONT};",
            css,
            count=1,
        )
    css_path.write_text(css)
    return out


def shift_palette(site_dir, out_dir, severity: float) -> Path:
    """Rotate every CSS hex color toward gray, by an amount growing with severity.

    Each ``#rrggbb`` is blended toward mid-gray (128) by ``severity``; at full
    severity the whole palette collapses to gray (maximal color drift), at 0 it is
    untouched. Editing the source (re-rendered) proves the ``color`` term responds
    to a *real* CSS palette change, not just a pixel filter.
    """
    out = _copy_site(site_dir, out_dir)
    css_path = out / "style.css"
    css = css_path.read_text()

    def blend(match):
        hexv = match.group(0)[1:]
        rgb = [int(hexv[i : i + 2], 16) for i in (0, 2, 4)]
        shifted = [round(c + (128 - c) * severity) for c in rgb]
        return "#" + "".join(f"{c:02x}" for c in shifted)

    css_path.write_text(re.sub(r"#[0-9a-fA-F]{6}", blend, css))
    return out


# --- Image-space perturbations -------------------------------------------------


def color_drift(img: Image.Image, severity: float) -> Image.Image:
    """Shift the whole palette in Lab space by an amount growing with severity.

    The drift is applied in CIE-Lab (perceptually uniform, the same space the
    ``color`` metric scores in) as a fixed-direction offset on the a*/b* chroma
    axes plus a mild lightness shift. Larger severity = larger ΔE from the
    reference palette, so the ``color`` term falls monotonically.
    """
    rgb = np.asarray(img.convert("RGB"), dtype=np.float64) / 255.0
    lab = rgb2lab(rgb)
    # Up to ~60 ΔE of chroma drift at full severity (a*,b* in ~[-128,127]).
    lab[..., 0] = np.clip(lab[..., 0] - 18.0 * severity, 0, 100)
    lab[..., 1] = np.clip(lab[..., 1] + 45.0 * severity, -128, 127)
    lab[..., 2] = np.clip(lab[..., 2] - 45.0 * severity, -128, 127)
    out = np.clip(lab2rgb(lab) * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def gaussian_blur(img: Image.Image, severity: float) -> Image.Image:
    """Gaussian-blur the image with a radius growing with severity.

    Blur destroys edges/structure, so SSIM (the ``structure`` term) falls as the
    radius grows. Severity 0 -> radius 0 (an exact copy).
    """
    radius = 6.0 * severity
    return img.convert("RGB").filter(ImageFilter.GaussianBlur(radius))


def spatial_shift(img: Image.Image, severity: float) -> Image.Image:
    """Translate the content down-and-right, exposing white, growing with severity.

    A rigid shift misaligns every edge with the reference (SSIM is shift
    sensitive), so the ``structure`` term falls as the offset grows. The vacated
    border is filled white (the page background) rather than wrapped, so it reads
    as a genuine layout offset, not a tile.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    # Up to ~12% of each dimension at full severity.
    dx = int(round(0.12 * w * severity))
    dy = int(round(0.12 * h * severity))
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(rgb, (dx, dy))
    return canvas


def region_occlusion(img: Image.Image, severity: float) -> Image.Image:
    """Cover a centered rectangle with a solid block, growing with severity.

    A growing occlusion hides more of the design (structure, and any text under
    it), so the relevant terms fall as the covered fraction grows. The block is
    mid-gray so it is clearly foreign to the page. Severity 0 covers nothing.
    """
    rgb = img.convert("RGB").copy()
    w, h = rgb.size
    # Covered side length as a fraction of each dimension (0 -> ~70%).
    fw = int(round(0.7 * w * severity))
    fh = int(round(0.7 * h * severity))
    if fw > 0 and fh > 0:
        x0 = (w - fw) // 2
        y0 = (h - fh) // 2
        ImageDraw.Draw(rgb).rectangle(
            [x0, y0, x0 + fw, y0 + fh], fill=(128, 128, 128)
        )
    return rgb


def pixel_noise(img: Image.Image, severity: float) -> Image.Image:
    """Add deterministic uniform pixel noise, amplitude growing with severity.

    Noise corrupts every pixel, degrading structure and color together. A fixed
    RNG seed keeps it reproducible (a hard requirement for the deterministic
    study). Severity 0 adds no noise.
    """
    arr = np.asarray(img.convert("RGB"), dtype=np.int16)
    rng = np.random.default_rng(_NOISE_SEED)
    amplitude = 120.0 * severity
    noise = rng.uniform(-amplitude, amplitude, size=arr.shape)
    out = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


# Fixed seed for pixel_noise so the same severity always yields the same image.
_NOISE_SEED = 0


# --- Degenerate generators -----------------------------------------------------
#
# These take no reference content — they are the anti-gaming floor. ``size`` is
# ``(width, height)`` to match PIL's convention.


def blank_page(size=(1280, 800)) -> Image.Image:
    """A pure-white page — the "rendered nothing" degenerate."""
    return Image.new("RGB", size, (255, 255, 255))


def solid_color(size=(1280, 800), color=(128, 128, 128)) -> Image.Image:
    """A single-color fill — the mean-gray anti-gaming case at the default color.

    A mid-gray fill is the classic "match the average color, replicate nothing"
    attack; the ``color`` term alone treats it generously (≈0.67 against a
    black/white-heavy reference, since one gray sits ~ΔE 33 from both extremes),
    but the aggregate floors it because structure/content/judge all collapse.
    """
    return Image.new("RGB", size, color)


# A short Lorem Ipsum body — canonical filler so "lorem"/"ipsum" are present.
_LOREM = (
    "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate."
)


def lorem_ipsum(size=(1280, 800)) -> Image.Image:
    """A white page of large dark Lorem-Ipsum filler text.

    This is the "right vibe, wrong substance" degenerate: it is plainly a text
    page (so a naive judge or content-by-presence check might be fooled), but the
    words match no reference, so ``content`` (OCR F1) collapses and the aggregate
    floors it. Rendered with a real TrueType font at a large size so the filler is
    legible to Tesseract.
    """
    img = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _legible_font(40)
    # Wrap the body to the page width by characters-per-line estimate.
    words = _LOREM.split()
    line, y = "", 30
    max_w = size[0] - 60
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) > max_w and line:
            draw.text((30, y), line, fill=(20, 20, 20), font=font)
            y += 56
            line = word
        else:
            line = trial
    if line:
        draw.text((30, y), line, fill=(20, 20, 20), font=font)
    return img


# Fonts the lorem/legible text fall back through; first that loads wins. Arial
# ships on macOS at the first path; DejaVu ships with many Linux distros and is
# bundled with matplotlib, so this stays portable to the verifier container.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _legible_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    # Last resort: matplotlib always ships DejaVuSans.
    import matplotlib

    mpl_font = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
    return ImageFont.truetype(str(mpl_font), size)
