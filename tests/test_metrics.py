"""Behavioral tests for the `structure` (SSIM) metric.

These assert external behavior: the float score a given image pair produces.
They never inspect intermediate arrays or library calls.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from webdesign_rl.grade.metrics import color, content, structure

# A real TrueType font at a large size so Tesseract reads the text reliably.
_FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 40)


def _text_image(lines, size=(640, 360)):
    """A white image with ``lines`` of large dark text (legible to OCR)."""
    img = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((20, 20 + i * 60), line, fill=(0, 0, 0), font=_FONT)
    return img


def _structured_reference():
    """A deterministic image with edges (checker-ish blocks) so SSIM is sensitive."""
    arr = np.full((64, 64), 255, dtype=np.uint8)
    arr[8:24, 8:24] = 0
    arr[40:56, 40:56] = 0
    arr[8:24, 40:56] = 120
    return Image.fromarray(arr).convert("RGB")


def _solid(size, color):
    """A solid-color RGB image of the given (w, h)."""
    return Image.new("RGB", size, color)


def test_identical_images_score_one():
    img = _solid((64, 48), (120, 30, 200))
    assert structure(img, img) == 1.0


def test_clearly_different_image_scores_meaningfully_lower():
    # A structured reference (a black square on white) versus an unrelated
    # candidate (vertical stripes) should score well below a perfect match.
    reference = np.full((48, 64), 255, dtype=np.uint8)
    reference[12:36, 20:44] = 0
    reference_img = Image.fromarray(reference).convert("RGB")

    stripes = np.zeros((48, 64), dtype=np.uint8)
    stripes[:, ::2] = 255
    candidate_img = Image.fromarray(stripes).convert("RGB")

    assert structure(candidate_img, reference_img) < 0.5


def test_ssim_decreases_monotonically_under_increasing_blur():
    reference = _structured_reference()
    scores = [
        structure(reference.filter(ImageFilter.GaussianBlur(radius)), reference)
        for radius in (0, 1, 2, 4, 8)
    ]
    assert scores == sorted(scores, reverse=True)
    # And the strongest blur is clearly worse than no blur.
    assert scores[-1] < scores[0]


def _shift_right(img, dx):
    """Roll the image content horizontally by dx pixels (deterministic)."""
    arr = np.asarray(img)
    return Image.fromarray(np.roll(arr, dx, axis=1))


def test_ssim_decreases_monotonically_under_increasing_shift():
    reference = _structured_reference()
    scores = [
        structure(_shift_right(reference, dx), reference)
        for dx in (0, 1, 2, 4, 8)
    ]
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] < scores[0]


def test_candidate_resized_to_reference_dimensions():
    # Same content at a different resolution must not be rejected for shape
    # mismatch; it is resized to the reference and scores near-perfect.
    reference = _structured_reference()  # 64x64
    candidate = reference.resize((128, 96), Image.Resampling.NEAREST)
    assert structure(candidate, reference) > 0.9


# --- color (k-means palette + CIEDE2000) -----------------------------------


def _palette_image(colors, size=(64, 64)):
    """A deterministic image whose pixels are an even split of ``colors``.

    Vertical bands of equal width, one per color, so the dominant palette is
    exactly ``colors`` at equal frequency.
    """
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    band = w // len(colors)
    for i, c in enumerate(colors):
        x0 = i * band
        x1 = w if i == len(colors) - 1 else (i + 1) * band
        arr[:, x0:x1] = c
    return Image.fromarray(arr, "RGB")


def test_identical_palette_scores_near_one():
    img = _palette_image([(200, 30, 30), (30, 200, 30), (30, 30, 200)])
    assert color(img, img) > 0.99


def test_hue_shifted_variant_scores_lower_than_identical():
    reference = _palette_image([(200, 30, 30), (30, 200, 30), (30, 30, 200)])
    # Genuinely different hues (orange / teal / purple) — none present in the
    # reference, so the matched ΔE is non-trivial and the score drops.
    shifted = _palette_image([(200, 120, 30), (30, 200, 200), (120, 30, 200)])
    assert color(shifted, reference) < color(reference, reference)


def test_color_decreases_monotonically_as_palette_drifts():
    base = [(200, 30, 30), (30, 200, 30), (30, 30, 200)]
    reference = _palette_image(base)
    # Progressively pull every palette color toward gray (128): a growing,
    # well-ordered perceptual drift.
    scores = []
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        drifted = [
            tuple(round(c + t * (128 - c)) for c in band) for band in base
        ]
        scores.append(color(_palette_image(drifted), reference))
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] < scores[0]


def test_color_is_deterministic_across_runs():
    reference = _palette_image([(200, 30, 30), (30, 200, 30), (30, 30, 200)])
    candidate = _palette_image([(200, 120, 30), (30, 200, 200), (120, 30, 200)])
    first = color(candidate, reference)
    second = color(candidate, reference)
    assert first == second


def test_color_not_gameable_by_matching_mean_color():
    # Reference: half black, half white (mean = mid-gray), a bold two-tone
    # palette. Candidate: uniform mid-gray — identical *average* color, totally
    # different *palette*. A faithful candidate keeps the black/white palette.
    # The mean-matching gray must score well below the faithful one, proving the
    # term reads the palette, not the average.
    reference = _palette_image([(0, 0, 0), (255, 255, 255)])
    faithful = _palette_image([(0, 0, 0), (255, 255, 255)])
    gray = Image.new("RGB", (64, 64), (128, 128, 128))
    assert color(gray, reference) < color(faithful, reference) - 0.2


# --- content (Tesseract OCR + word-multiset F1) -----------------------------


def test_identical_text_scores_near_one():
    img = _text_image(["Welcome Home", "Get Started Today"])
    assert content(img, img) > 0.99


def test_removing_words_lowers_score():
    reference = _text_image(["Welcome Home", "Get Started Today"])
    # Candidate keeps only the first line: half the reference words are missing,
    # so recall (and therefore the F1) drops below a faithful copy.
    candidate = _text_image(["Welcome Home"])
    assert content(candidate, reference) < content(reference, reference)


def test_injecting_words_lowers_score():
    reference = _text_image(["Welcome Home"])
    # Candidate has the reference text plus hallucinated extra words: precision
    # drops (the extra words match nothing), pulling the F1 below a faithful copy.
    candidate = _text_image(["Welcome Home", "Buy Now Cheap Deals"])
    assert content(candidate, reference) < content(reference, reference)


def test_empty_candidate_scores_zero():
    reference = _text_image(["Welcome Home", "Get Started Today"])
    # A blank candidate has no text: recall is 0, so the score floors at 0.
    blank = Image.new("RGB", (640, 360), (255, 255, 255))
    assert content(blank, reference) == 0.0


def test_content_is_deterministic_across_runs():
    reference = _text_image(["Welcome Home", "Get Started Today"])
    candidate = _text_image(["Welcome Home", "Buy Now"])
    assert content(candidate, reference) == content(candidate, reference)


def test_order_does_not_change_score():
    # Word-multiset F1 is order-robust: shuffling lines scores the same as the
    # identical-text copy (the words present are unchanged).
    reference = _text_image(["Welcome Home", "Get Started Today"])
    reordered = _text_image(["Get Started Today", "Welcome Home"])
    assert content(reordered, reference) == content(reference, reference)


def test_committed_text_fixture_is_ocr_legible():
    # Guard against a silently-empty fixture: OCR the committed text page and
    # assert the exact words it was generated with actually come out. If this
    # fails, the fixture is unreadable and every other content test is hollow.
    from pathlib import Path

    import pytesseract

    from fixtures import _generate

    path = Path(_generate.__file__).parent / "text" / "reference.png"
    extracted = set(pytesseract.image_to_string(Image.open(path)).lower().split())
    expected = {w for line in _generate.TEXT_LINES for w in line.lower().split()}
    assert expected <= extracted, f"OCR missed words: {expected - extracted}"
