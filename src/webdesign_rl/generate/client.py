"""The thin, stubbable LLM boundary every generation stage calls through.

Mirrors the grader's ``JudgeClient`` pattern (see ``grade/judge.py``): all the
nondeterminism and network I/O of generation lives behind a single
``complete(prompt, *, temperature) -> str`` method. The deterministic logic
around it — prompt assembly, response parsing, and composing the three stage
outputs into a renderable site — is therefore fully testable with
:class:`StubGenerationClient` and **no live API call**.

The real :class:`AnthropicGenerationClient` is import-safe (the ``anthropic`` SDK
is imported lazily) and is only used when explicitly injected. Generation uses a
single model — **Opus 4.6** — across all three stages, with the per-stage
temperature passed in by the caller (1.0 / 0.7 / 0.6 for stages 1/2/3).
"""

import logging
import time
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Single generation model for all three stages (design decision #10). The
# canonical model list spells out ``claude-opus-4-8``; the SDK's ``Model`` literal
# also accepts ``claude-opus-4-6``, so this exact ID is valid to wire.
GENERATION_MODEL = "claude-opus-4-6"

# Transient HTTP statuses worth a backed-off retry: rate-limit (429), the
# Anthropic "overloaded_error" (529), and any 5xx. Auth (401) / bad-request
# (400) and other 4xx are NOT transient and must surface immediately.
_TRANSIENT_STATUS = frozenset({408, 409, 429, 529})


def _is_transient(exc) -> bool:
    """Whether an exception from the Messages API is worth retrying.

    Classified by HTTP ``status_code`` (so it works for both the SDK's typed
    errors and any thin stand-in): 429 / 529 / 5xx are transient; 4xx like
    400 (bad request) and 401 (auth) are not.

    With no HTTP status, retry **only** a genuine connection/timeout error.
    A synchronous client-side error raised before any network round-trip — e.g.
    the SDK's ``ValueError`` demanding streaming for a large ``max_tokens``, or
    any request-validation failure — is deterministic: retrying it just burns
    the budget on the same failure, so it must surface immediately.
    """
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status in _TRANSIENT_STATUS or status >= 500
    try:
        import anthropic  # lazy: only needed to classify a live SDK error.

        # APITimeoutError subclasses APIConnectionError, so this covers timeouts.
        if isinstance(exc, anthropic.APIConnectionError):
            return True
    except Exception:
        pass
    return isinstance(exc, (ConnectionError, TimeoutError))


@runtime_checkable
class GenerationClient(Protocol):
    """Boundary for the generation LLM: a prompt + temperature -> a text response.

    The only seam the deterministic pipeline depends on, which is what makes the
    stages stubbable without live API calls.
    """

    def complete(self, prompt: str, *, temperature: float) -> str:
        """Return the model's text response to ``prompt`` at ``temperature``."""
        ...


class StubGenerationClient:
    """A canned-response :class:`GenerationClient` for tests and offline runs.

    Returns its ``responses`` in order (one per ``complete`` call) and records the
    ``(prompt, temperature)`` pairs it was asked about, so the pipeline can be
    exercised end-to-end with no network access or API key.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self._index = 0
        self.calls = []

    def complete(self, prompt, *, temperature):
        self.calls.append((prompt, temperature))
        response = self._responses[self._index]
        self._index += 1
        return response


class AnthropicGenerationClient:
    """Real :class:`GenerationClient` backed by the Anthropic Messages API.

    Uses Opus 4.6 at the caller-supplied temperature with a single sample. The
    ``anthropic`` SDK is imported lazily so this module stays import-safe with no
    API key; the client is only ever used when explicitly injected.
    """

    def __init__(
        self,
        client=None,
        model: str = GENERATION_MODEL,
        max_tokens: int = 32000,
        *,
        max_retries: int = 4,
        backoff_base: float = 1.0,
    ):
        if client is None:
            import anthropic  # lazy: keep the module import-safe.

            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def _create_with_retry(self, **kwargs):
        """Call the Messages API, retrying transient errors with backoff.

        Retries 429 / 529 / 5xx (and bare connection errors) up to
        ``max_retries`` times with exponential backoff (``backoff_base * 2**k``
        seconds). Non-transient errors (auth, bad request) surface immediately;
        once the retry budget is exhausted the last transient error is raised.
        """
        attempt = 0
        while True:
            try:
                return self._create_message(**kwargs)
            except Exception as exc:
                if not _is_transient(exc) or attempt >= self._max_retries:
                    raise
                delay = self._backoff_base * (2 ** attempt)
                logger.warning(
                    "transient generation error (%s); retry %d/%d in %.1fs",
                    exc, attempt + 1, self._max_retries, delay,
                )
                if delay:
                    time.sleep(delay)
                attempt += 1

    def _create_message(self, **kwargs):
        """Create one message via the **streaming** API; return the final Message.

        Streaming — not a one-shot ``messages.create`` — because the SDK refuses
        a *non*-streaming request whose ``max_tokens`` could take over 10 minutes
        (any ``max_tokens`` above ~21k for this model, and the default cap is
        32k). ``get_final_message`` blocks until the stream completes and returns
        the accumulated :class:`Message` (with its ``stop_reason``), so the rest
        of the client — retry classification and truncation detection — is
        unchanged from the non-streaming path.
        """
        with self._client.messages.stream(**kwargs) as stream:
            return stream.get_final_message()

    def complete(self, prompt, *, temperature):
        message = self._create_with_retry(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        # A response cut off at the token cap (``stop_reason == "max_tokens"``)
        # is a partial output — returning it would hand a downstream parser a
        # truncated artifact (an unterminated JSON string / a missing ===FILE===
        # block). Surface it as a clear, actionable error instead.
        if getattr(message, "stop_reason", None) == "max_tokens":
            raise ValueError(
                f"generation response was truncated at max_tokens "
                f"({self._max_tokens}); the model hit the output cap before "
                "finishing. Raise max_tokens or shrink the requested output."
            )
        return "".join(
            block.text for block in message.content if block.type == "text"
        )
