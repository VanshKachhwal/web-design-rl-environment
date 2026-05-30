"""Behavioral tests for the perturbation module (Layer A: fast, deterministic).

These assert the *external* property the validation study relies on: a higher
severity level is more degraded on that perturbation's own axis. They measure the
degradation with the grader's own metrics where that is the axis under test, or
with an axis-appropriate direct measurement otherwise — never by inspecting
internals of the perturbation functions.
"""

import re

import numpy as np
from PIL import Image

from webdesign_rl.grade import metrics, perturb

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures"
REFERENCE_SITE = FIXTURES / "site_reference"


def _reference_image():
    """A small, structured, colorful reference image.

    Solid colored blocks on white give every axis something to degrade: distinct
    colors for the color term, edges for structure/blur, regions to occlude.
    """
    arr = np.full((120, 120, 3), 255, dtype=np.uint8)
    arr[10:40, 10:110] = (40, 60, 200)    # blue header
    arr[50:80, 10:55] = (200, 60, 40)     # red left
    arr[50:80, 65:110] = (40, 200, 60)    # green right
    arr[90:115, 10:110] = (30, 30, 30)    # dark footer
    return Image.fromarray(arr, "RGB")


def test_color_drift_lowers_color_metric_monotonically():
    ref = _reference_image()
    scores = [
        metrics.color(perturb.color_drift(ref, s), ref)
        for s in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    # Severity 0 is (near) perfect; each step drives the color term down.
    assert scores[0] > 0.95
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_gaussian_blur_lowers_structure_metric_monotonically():
    ref = _reference_image()
    scores = [
        metrics.structure(perturb.gaussian_blur(ref, s), ref)
        for s in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores[0] > 0.95
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_spatial_shift_lowers_structure_metric_monotonically():
    ref = _reference_image()
    scores = [
        metrics.structure(perturb.spatial_shift(ref, s), ref)
        for s in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores[0] > 0.95
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_region_occlusion_lowers_structure_metric_monotonically():
    ref = _reference_image()
    scores = [
        metrics.structure(perturb.region_occlusion(ref, s), ref)
        for s in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores[0] > 0.95
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_pixel_noise_lowers_structure_metric_monotonically():
    ref = _reference_image()
    scores = [
        metrics.structure(perturb.pixel_noise(ref, s), ref)
        for s in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert scores[0] > 0.95
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores
    assert scores[-1] < scores[0]


def test_pixel_noise_is_deterministic():
    ref = _reference_image()
    a = np.asarray(perturb.pixel_noise(ref, 0.7))
    b = np.asarray(perturb.pixel_noise(ref, 0.7))
    assert np.array_equal(a, b)


# --- Degenerate generators ----------------------------------------------------


def test_blank_page_is_all_white():
    arr = np.asarray(perturb.blank_page((80, 60)))
    assert arr.shape == (60, 80, 3)
    assert (arr == 255).all()


def test_solid_color_fills_the_requested_color():
    arr = np.asarray(perturb.solid_color((80, 60), (10, 20, 30)))
    assert arr.shape == (60, 80, 3)
    assert (arr.reshape(-1, 3) == (10, 20, 30)).all()


def test_lorem_ipsum_page_has_legible_filler_text():
    # The lorem page must actually contain readable text (it is the "right vibe,
    # wrong substance" degenerate), so OCR finds the canonical "lorem"/"ipsum".
    img = perturb.lorem_ipsum((640, 480))
    import pytesseract

    words = pytesseract.image_to_string(img).lower()
    assert "lorem" in words
    assert "ipsum" in words


# --- Source-space perturbations -----------------------------------------------
#
# These copy the reference site and apply a controlled edit; the study re-renders
# them. We assert the external property (the written source is correctly ordered
# on its axis) directly on the files — fast, no Chromium — rather than rendering.


def _words(text):
    return set(re.findall(r"[A-Za-z]+", text.lower()))


def _visible_text(html):
    """Approximate visible page text: strip tags/head, lowercase the body words."""
    body = re.sub(r"<head>.*?</head>", "", html, flags=re.S)
    return _words(re.sub(r"<[^>]+>", " ", body))


def test_delete_text_removes_more_words_as_severity_rises(tmp_path):
    ref_html = (REFERENCE_SITE / "index.html").read_text()
    ref_words = _visible_text(ref_html)

    kept = []
    for i, s in enumerate((0.0, 0.5, 1.0)):
        out = perturb.delete_text(REFERENCE_SITE, tmp_path / f"d{i}", s)
        html = (out / "index.html").read_text()
        kept.append(len(_visible_text(html) & ref_words))

    # Severity 0 keeps all the reference words; higher severity keeps fewer.
    assert kept[0] == len(ref_words)
    assert kept[0] >= kept[1] >= kept[2]
    assert kept[2] < kept[0]


def test_remove_element_drops_a_section_at_higher_severity(tmp_path):
    out0 = perturb.remove_element(REFERENCE_SITE, tmp_path / "r0", 0.0)
    out1 = perturb.remove_element(REFERENCE_SITE, tmp_path / "r1", 1.0)
    # Severity 0 leaves the markup intact; severity 1 removes at least one element
    # (fewer tags), so the rendered page is missing content.
    n0 = (out0 / "index.html").read_text().count("<section")
    n1 = (out1 / "index.html").read_text().count("<section")
    assert n0 == REFERENCE_SITE.joinpath("index.html").read_text().count("<section")
    assert n1 < n0


def test_swap_font_changes_the_font_family(tmp_path):
    out = perturb.swap_font(REFERENCE_SITE, tmp_path / "f", 1.0)
    ref_css = (REFERENCE_SITE / "style.css").read_text()
    css = (out / "style.css").read_text()
    # The body font-family declaration is changed to something else.
    assert "font-family" in css
    assert css != ref_css


def test_shift_palette_changes_more_colors_as_severity_rises(tmp_path):
    ref_css = (REFERENCE_SITE / "style.css").read_text()
    ref_hexes = re.findall(r"#[0-9a-fA-F]{6}", ref_css)

    changed = []
    for i, s in enumerate((0.0, 0.5, 1.0)):
        out = perturb.shift_palette(REFERENCE_SITE, tmp_path / f"p{i}", s)
        css = (out / "style.css").read_text()
        hexes = re.findall(r"#[0-9a-fA-F]{6}", css)
        changed.append(
            sum(1 for a, b in zip(ref_hexes, hexes) if a.lower() != b.lower())
        )

    assert changed[0] == 0          # severity 0 leaves the palette untouched
    assert changed[0] <= changed[1] <= changed[2]
    assert changed[2] > 0
