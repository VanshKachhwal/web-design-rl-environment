"""Behavioral tests for the ``design_judge`` VLM term.

The judge logic must be fully deterministic and testable with **no live API
calls**: the model call sits behind a thin client interface that these tests
stub with canned rubrics. We assert only that a stubbed rubric parses into the
correct averaged [0, 1] score and that malformed responses are handled
gracefully — never live model output.
"""

import base64
import io

from PIL import Image

from webdesign_rl.grade.judge import (
    JudgeClient,
    StubJudgeClient as ModuleStubJudgeClient,
    _MAX_EDGE,
    _encode_png,
    design_judge,
    judge_rubric,
)


def _decode_png(encoded: str) -> Image.Image:
    """Round-trip the base64 PNG the judge would send back into a PIL image."""
    return Image.open(io.BytesIO(base64.b64decode(encoded)))


def test_encode_png_downscales_tall_image_under_max_edge():
    # A real reference render can be 1280x11706 — taller than the API's 8000px
    # cap, which 400s. The encoded bytes must come back within the cap.
    tall = Image.new("RGB", (1280, 11706), (10, 20, 30))
    decoded = _decode_png(_encode_png(tall))
    assert decoded.width <= _MAX_EDGE
    assert decoded.height <= _MAX_EDGE
    # Aspect ratio is preserved within rounding tolerance.
    src_ratio = 1280 / 11706
    out_ratio = decoded.width / decoded.height
    assert abs(src_ratio - out_ratio) < 0.01


def test_encode_png_leaves_small_image_dimensions_unchanged():
    # A page within the cap (1280x800) is encoded at its native size — never
    # upscaled, never shrunk.
    small = Image.new("RGB", (1280, 800), (200, 100, 50))
    decoded = _decode_png(_encode_png(small))
    assert decoded.size == (1280, 800)


def test_encode_png_does_not_mutate_input_image():
    # grade() persists the ORIGINAL full-res images; the downscale must only
    # touch the encoded copy, never the passed-in object.
    tall = Image.new("RGB", (1280, 11706), (10, 20, 30))
    _encode_png(tall)
    assert tall.size == (1280, 11706)


class StubJudgeClient:
    """A fake judge client returning a canned rubric, for deterministic tests."""

    def __init__(self, rubric):
        self._rubric = rubric
        self.calls = []

    def score(self, reference_img, candidate_img):
        self.calls.append((reference_img, candidate_img))
        return self._rubric


def _img():
    return Image.new("RGB", (4, 4), (128, 128, 128))


def test_all_tens_rubric_scores_one():
    client = StubJudgeClient(
        {
            "layout_alignment": 10,
            "color_palette": 10,
            "typography": 10,
            "content_completeness": 10,
        }
    )
    score = design_judge(_img(), _img(), client)
    assert score == 1.0


def test_all_zeros_rubric_scores_zero():
    client = StubJudgeClient(
        {
            "layout_alignment": 0,
            "color_palette": 0,
            "typography": 0,
            "content_completeness": 0,
        }
    )
    assert design_judge(_img(), _img(), client) == 0.0


def test_mixed_rubric_averages_then_normalizes_by_ten():
    client = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    # mean(8, 6, 10, 4) = 7.0 -> /10 = 0.7
    assert design_judge(_img(), _img(), client) == 0.7


def test_judge_rubric_records_normalized_sub_scores_and_overall():
    client = StubJudgeClient(
        {
            "layout_alignment": 8,
            "color_palette": 6,
            "typography": 10,
            "content_completeness": 4,
        }
    )
    result = judge_rubric(_img(), _img(), client)
    # Overall is the averaged [0, 1] term...
    assert result["design_judge"] == 0.7
    # ...and each sub-score is recorded, normalized to [0, 1], for logging.
    assert result["sub_scores"] == {
        "layout_alignment": 0.8,
        "color_palette": 0.6,
        "typography": 1.0,
        "content_completeness": 0.4,
    }


def test_missing_rubric_field_is_treated_as_zero():
    # The judge omitted ``typography`` entirely; it must not crash and the
    # missing dimension scores 0 (the conservative floor).
    client = StubJudgeClient(
        {
            "layout_alignment": 10,
            "color_palette": 10,
            "content_completeness": 10,
        }
    )
    result = judge_rubric(_img(), _img(), client)
    assert result["sub_scores"]["typography"] == 0.0
    # mean(1.0, 1.0, 0.0, 1.0) = 0.75
    assert result["design_judge"] == 0.75


def test_non_numeric_rubric_value_is_treated_as_zero():
    client = StubJudgeClient(
        {
            "layout_alignment": "great",
            "color_palette": None,
            "typography": 10,
            "content_completeness": 10,
        }
    )
    result = judge_rubric(_img(), _img(), client)
    assert result["sub_scores"]["layout_alignment"] == 0.0
    assert result["sub_scores"]["color_palette"] == 0.0
    # mean(0.0, 0.0, 1.0, 1.0) = 0.5
    assert result["design_judge"] == 0.5


def test_out_of_range_rubric_value_is_clamped():
    # A judge that returns 15 or -3 must not push the term outside [0, 1].
    client = StubJudgeClient(
        {
            "layout_alignment": 15,
            "color_palette": -3,
            "typography": 10,
            "content_completeness": 0,
        }
    )
    result = judge_rubric(_img(), _img(), client)
    assert result["sub_scores"]["layout_alignment"] == 1.0
    assert result["sub_scores"]["color_palette"] == 0.0
    assert 0.0 <= result["design_judge"] <= 1.0


def test_non_dict_rubric_response_scores_zero():
    # A wholly malformed response (not even a mapping) must not crash; every
    # dimension floors to 0.
    for bad in (None, [], "nope", 5):
        client = StubJudgeClient(bad)
        result = judge_rubric(_img(), _img(), client)
        assert result["design_judge"] == 0.0
        assert all(v == 0.0 for v in result["sub_scores"].values())


def test_module_stub_client_satisfies_the_judge_client_interface():
    # The shipped StubJudgeClient is a drop-in JudgeClient returning canned
    # rubrics, usable by both tests and the grader without live API calls.
    stub = ModuleStubJudgeClient(
        {
            "layout_alignment": 10,
            "color_palette": 10,
            "typography": 10,
            "content_completeness": 10,
        }
    )
    assert isinstance(stub, JudgeClient)
    assert design_judge(_img(), _img(), stub) == 1.0
