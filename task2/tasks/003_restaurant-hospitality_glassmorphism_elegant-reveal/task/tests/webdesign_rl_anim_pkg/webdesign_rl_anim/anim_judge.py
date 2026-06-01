"""LLM-as-judge for *animation* fidelity over a pair of filmstrip contact sheets.

Mirrors Task 1's ``grade/judge.py`` exactly in shape — a thin :class:`AnimationJudgeClient`
boundary with a single ``score`` method, deterministic rubric parsing/normalising
around it, a :class:`StubAnimationJudgeClient` for offline/test use, and a real
Anthropic-backed client whose SDK import is lazy. The difference is *what* it
judges: instead of static design, it rates how faithfully the candidate's motion
matches the reference's, from the two contact sheets (each a vertical strip of
captioned frames).

The rubric is four 0-10 sub-scores, averaged and normalised to [0, 1]:

* ``motion_presence`` — do the same elements animate (vs a static candidate)?
* ``timing`` — do motions start / peak / settle at similar points across the strip?
* ``easing_feel`` — similar acceleration/deceleration character?
* ``motion_type`` — same *kind* of motion (fade / slide / scale / loop) per element?

A Sonnet-class model is used (distinct from the Opus agent under test) to avoid
self-preference bias — the same rationale as the design judge.
"""

import base64
import io
import json

from PIL import Image

RUBRIC_FIELDS = (
    "motion_presence",
    "timing",
    "easing_feel",
    "motion_type",
)

# Sonnet-class judge, distinct from the Opus agent under test (anti-self-preference).
JUDGE_MODEL = "claude-sonnet-4-6"

# Vision API hard-rejects images with any edge > 8000px; contact sheets of tall
# pages can exceed that, so the judge-bound copy is downscaled to fit.
_MAX_EDGE = 8000

_RUBRIC_PROMPT = (
    "You are grading how faithfully a CANDIDATE web page reproduces the ANIMATION "
    "of a REFERENCE web page. Each image is a CONTACT SHEET: vertically stacked "
    "frames of one page captured at increasing times (the 't = N ms' caption above "
    "each frame). The first image is the REFERENCE filmstrip; the second is the "
    "CANDIDATE filmstrip, captured at the SAME times. Read top-to-bottom to see how "
    "each page animates over time.\n"
    "Score the CANDIDATE against the REFERENCE on four criteria, each an integer "
    "from 0 (completely wrong / no animation) to 10 (indistinguishable motion):\n"
    "- motion_presence: do the same elements animate at all (a static candidate scores 0)?\n"
    "- timing: do animations begin, peak, and settle at similar times across the strip?\n"
    "- easing_feel: similar acceleration/deceleration character (ease vs linear, snappy vs slow)?\n"
    "- motion_type: same KIND of motion per element (fade, slide, scale, rotate, looping pulse)?\n"
    "Do NOT analyze, narrate, or explain. Your ENTIRE reply must be a single JSON "
    "object with exactly these four integer keys and nothing else — begin your "
    'reply with the "{" character. Example: '
    '{"motion_presence": 8, "timing": 6, "easing_feel": 7, "motion_type": 9}'
)


def _normalize(raw) -> float:
    """Coerce one raw 0-10 sub-score into [0, 1], flooring malformed values to 0."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, value)) / 10.0


def judge_rubric(reference_sheet, candidate_sheet, client) -> dict:
    """Score candidate-vs-reference motion and return the full breakdown.

    Returns ``{"animation_judge": float, "sub_scores": {field: float, ...}}``.
    """
    rubric = client.score(reference_sheet, candidate_sheet)
    if not isinstance(rubric, dict):
        rubric = {}
    sub_scores = {f: _normalize(rubric.get(f)) for f in RUBRIC_FIELDS}
    overall = sum(sub_scores.values()) / len(sub_scores)
    return {"animation_judge": overall, "sub_scores": sub_scores}


class StubAnimationJudgeClient:
    """Canned-rubric client for tests / offline grading; records its calls."""

    def __init__(self, rubric):
        self.rubric = rubric
        self.calls = []

    def score(self, reference_sheet, candidate_sheet):
        self.calls.append((reference_sheet, candidate_sheet))
        return self.rubric


def _downscaled(img: Image.Image) -> Image.Image:
    longest = max(img.size)
    if longest <= _MAX_EDGE:
        return img
    scale = _MAX_EDGE / longest
    w, h = img.size
    return img.resize((min(_MAX_EDGE, round(w * scale)),
                       min(_MAX_EDGE, round(h * scale))), Image.LANCZOS)


def _encode_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    _downscaled(img).convert("RGB").save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


class AnthropicAnimationJudgeClient:
    """Real :class:`AnimationJudgeClient` backed by the Anthropic vision API.

    Sonnet-class model, temperature 0, single sample; passes the reference and
    candidate contact sheets and requests the JSON rubric. The ``anthropic`` SDK
    is imported lazily so this module is import-safe with no API key.
    """

    def __init__(self, client=None, model: str = JUDGE_MODEL):
        if client is None:
            import anthropic  # lazy: keep the module import-safe.

            client = anthropic.Anthropic()
        self._client = client
        self._model = model

    def score(self, reference_sheet, candidate_sheet):
        # A verbose model wants to narrate a long frame-by-frame analysis before
        # the rubric. This model rejects assistant-prefill, so we instead (a) tell
        # it firmly to emit JSON only and (b) give a generous max_tokens so that
        # even if it prepends a line, the JSON object still lands inside the cap
        # (``_parse_rubric_text`` then extracts the object). 256 tokens truncated
        # the JSON entirely and floored every term to 0.
        message = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "REFERENCE filmstrip:"},
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png",
                            "data": _encode_png(reference_sheet)}},
                        {"type": "text", "text": "CANDIDATE filmstrip:"},
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png",
                            "data": _encode_png(candidate_sheet)}},
                        {"type": "text", "text": _RUBRIC_PROMPT},
                    ],
                },
            ],
        )
        return _parse_rubric_text("".join(
            block.text for block in message.content if block.type == "text"
        ))


def _parse_rubric_text(text: str) -> dict:
    """Extract the first ``{...}`` JSON object; ``{}`` on failure (floors to 0)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        parsed = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
