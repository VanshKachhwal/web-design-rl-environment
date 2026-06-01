"""A generation client that continues truncated responses WITHOUT prefill.

The generation model (``claude-opus-4-6``) rejects assistant-message **prefill**
(ending a request on an assistant turn) — which is exactly the continuation
strategy Task 1's :class:`AnthropicGenerationClient` uses, so the moment a response
hits ``max_tokens`` it 400s. This subclass keeps all of Task 1's robust machinery
(streaming, transient-error retry/backoff, overlap-trim — reused read-only) and only
changes *how* it continues: it re-sends the conversation as

    [user: original prompt] → [assistant: partial so far] → [user: "continue…"]

so every request **ends with a user message** (valid for this model) rather than a
prefilled assistant turn. The continuation chunks are stitched with the parent's
``_trim_overlap`` so a re-emitted seam doesn't duplicate. The result: a response of
any length completes by continuing the conversation, robustly, with no prefill.
"""

from webdesign_rl.generate.client import AnthropicGenerationClient

# Default continuation budget: generous enough that even a very large shared design
# system (plan + styles.css + animations.css + partials) completes. Each round can
# add up to ``max_tokens`` more, so 6 rounds ≈ up to ~190k tokens of output.
DEFAULT_MAX_CONTINUATIONS = 6

_CONTINUE_MSG = (
    "Continue exactly where you left off, picking up mid-token if needed. Output "
    "ONLY the remaining content verbatim — do NOT repeat any earlier text, and do "
    "NOT add any preamble, explanation, or code fences."
)


class ContinuingGenerationClient(AnthropicGenerationClient):
    """Like Task 1's client, but continues via a trailing USER turn (no prefill)."""

    def __init__(self, *args, max_continuations: int = DEFAULT_MAX_CONTINUATIONS, **kwargs):
        super().__init__(*args, max_continuations=max_continuations, **kwargs)

    def complete(self, prompt, *, temperature):
        messages = [{"role": "user", "content": prompt}]
        accumulated = ""
        for _ in range(self._max_continuations + 1):
            message = self._create_with_retry(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=temperature,
                messages=messages,
            )
            chunk = self._message_text(message)
            accumulated += self._trim_overlap(accumulated, chunk) if accumulated else chunk

            if getattr(message, "stop_reason", None) != "max_tokens":
                return accumulated

            # Truncated → continue, but END ON A USER MESSAGE (not prefill): replay
            # the prompt, the partial answer, and a user instruction to continue.
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": accumulated},
                {"role": "user", "content": _CONTINUE_MSG},
            ]

        raise ValueError(
            f"generation response still truncated after {self._max_continuations} "
            f"prefill-free continuation(s) at max_tokens={self._max_tokens}; the "
            "output is implausibly large — shrink the requested output."
        )
