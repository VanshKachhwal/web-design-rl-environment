"""LLM-as-judge design-fidelity scoring over candidate/reference screenshot pairs.

The ``design_judge`` term is the one non-deterministic grader dimension: a single
vision-LLM call scores the candidate against the reference on a small numeric
rubric (layout/alignment, color/palette, typography, content-completeness, each
0-10), which is averaged and normalized into one [0, 1] score.

All of that nondeterminism and I/O lives behind the :class:`JudgeClient`
interface — a thin boundary with a single ``score`` method. The deterministic
logic (rubric parsing, averaging, edge-case handling) is therefore fully
testable with the :class:`StubJudgeClient` and **no live API calls**. The real
:class:`AnthropicJudgeClient` is import-safe (the SDK is imported lazily) and is
only used when explicitly injected into the grader.
"""

import base64
import io
import json
from typing import Protocol, runtime_checkable

from PIL import Image

# The four rubric sub-scores the judge returns, each anchored 0-10. Their mean,
# normalized to [0, 1], is the ``design_judge`` term.
RUBRIC_FIELDS = (
    "layout_alignment",
    "color_palette",
    "typography",
    "content_completeness",
)


@runtime_checkable
class JudgeClient(Protocol):
    """Boundary for the vision-LLM judge: maps an image pair to a raw rubric.

    Implementations return a mapping of ``RUBRIC_FIELDS`` to raw 0-10 scores
    (parsing/normalization is the module's job, so clients stay thin). This is
    the only seam the deterministic scoring logic depends on, which is what makes
    the term stubbable without live API calls.
    """

    def score(
        self, reference_img: Image.Image, candidate_img: Image.Image
    ) -> dict:
        """Return a raw ``{field: 0-10}`` rubric for the candidate vs reference."""
        ...


def _normalize(raw) -> float:
    """Coerce one raw 0-10 sub-score into a [0, 1] float, defensively.

    The judge is a fallible LLM: a field may be missing, non-numeric, or out of
    range. Rather than crash grading, a malformed value scores 0 (the
    conservative floor) and an out-of-range number is clamped to [0, 10].
    """
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, value)) / 10.0


def judge_rubric(candidate_img, reference_img, client) -> dict:
    """Score the candidate against the reference and return the full breakdown.

    The ``client`` returns a raw rubric of four 0-10 sub-scores
    (``RUBRIC_FIELDS``). This normalizes each to [0, 1] and averages them into
    the overall ``design_judge`` term, returning both so the grader can log the
    sub-scores to ``reward-details.json``::

        {"design_judge": float, "sub_scores": {field: float, ...}}
    """
    rubric = client.score(reference_img, candidate_img)
    if not isinstance(rubric, dict):
        rubric = {}
    sub_scores = {field: _normalize(rubric.get(field)) for field in RUBRIC_FIELDS}
    overall = sum(sub_scores.values()) / len(sub_scores)
    return {"design_judge": overall, "sub_scores": sub_scores}


def design_judge(candidate_img, reference_img, client) -> float:
    """Score holistic design fidelity in [0, 1] via a (stubbable) VLM client.

    Convenience wrapper over :func:`judge_rubric` returning just the averaged,
    normalized [0, 1] term.
    """
    return judge_rubric(candidate_img, reference_img, client)["design_judge"]


class StubJudgeClient:
    """A canned-rubric :class:`JudgeClient` for tests and offline grading.

    Returns the same rubric on every call and records the image pairs it was
    asked about, so the deterministic scoring logic can be exercised with no
    network access or API key.
    """

    def __init__(self, rubric):
        self.rubric = rubric
        self.calls = []

    def score(self, reference_img, candidate_img):
        self.calls.append((reference_img, candidate_img))
        return self.rubric


# The judge model is deliberately a Sonnet-class model, distinct from the Opus
# agent under test, to avoid self-preference bias (design decision #4).
JUDGE_MODEL = "claude-sonnet-4-6"

_RUBRIC_PROMPT = (
    "You are grading how faithfully a CANDIDATE web page replicates a REFERENCE "
    "web design. The first image is the REFERENCE; the second is the CANDIDATE. "
    "Score the CANDIDATE against the REFERENCE on four criteria, each an integer "
    "from 0 (completely wrong) to 10 (indistinguishable):\n"
    "- layout_alignment: arrangement, spacing, and alignment of elements\n"
    "- color_palette: colors, backgrounds, and overall palette\n"
    "- typography: fonts, sizes, weights, and text styling\n"
    "- content_completeness: presence and correctness of the text/content\n"
    "Respond with ONLY a JSON object with exactly these four integer keys, "
    'e.g. {"layout_alignment": 7, "color_palette": 8, "typography": 6, '
    '"content_completeness": 9}.'
)


def _encode_png(img: Image.Image) -> str:
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="PNG")
    return base64.standard_b64encode(buffer.getvalue()).decode("ascii")


class AnthropicJudgeClient:
    """Real :class:`JudgeClient` backed by the Anthropic vision API.

    Uses a Sonnet-class model (distinct from the Opus agent under test) at
    temperature 0 with a single sample, passing both screenshots labeled
    REFERENCE and CANDIDATE and requesting a JSON rubric. The ``anthropic`` SDK
    is imported lazily so this module stays import-safe with no API key; the
    client is only ever used when explicitly injected into the grader.
    """

    def __init__(self, client=None, model: str = JUDGE_MODEL):
        if client is None:
            import anthropic  # lazy: keep the module import-safe.

            client = anthropic.Anthropic()
        self._client = client
        self._model = model

    def score(self, reference_img, candidate_img):
        message = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "REFERENCE:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": _encode_png(reference_img),
                            },
                        },
                        {"type": "text", "text": "CANDIDATE:"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": _encode_png(candidate_img),
                            },
                        },
                        {"type": "text", "text": _RUBRIC_PROMPT},
                    ],
                }
            ],
        )
        return _parse_rubric_text("".join(
            block.text for block in message.content if block.type == "text"
        ))


def _parse_rubric_text(text: str) -> dict:
    """Extract the rubric JSON object from the model's text response.

    Tolerant of surrounding prose / code fences: locates the first ``{...}`` and
    parses it. A response with no parseable object yields ``{}``, which the
    deterministic scorer floors to 0 — so a malformed judge reply never crashes
    grading.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        parsed = json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
