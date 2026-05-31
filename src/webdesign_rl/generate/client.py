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

# Server-side transient error *body* types. The streaming API can surface an
# "overloaded" as an in-stream SSE ``error`` event on an HTTP-200 stream (the
# stream opened, then errored), so the resulting ``APIStatusError`` carries
# ``status_code == 200`` and the real signal lives only in its parsed ``body``
# (``body["error"]["type"]``). These types mean the server is transiently
# unavailable and are worth a backed-off retry; client-error types
# (``invalid_request_error`` / ``authentication_error``) must stay non-transient.
_TRANSIENT_ERROR_TYPES = frozenset({"overloaded_error", "api_error"})

# Cap on the continuation-seam overlap scan (chars). Far larger than any
# realistic re-emitted tail / re-opened ``===FILE===`` marker, but small enough
# that trimming stays cheap against a ~100KB truncated chunk.
_MAX_OVERLAP_SCAN = 4096


def _is_transient(exc) -> bool:
    """Whether an exception from the Messages API is worth retrying.

    Classified by HTTP ``status_code`` (so it works for both the SDK's typed
    errors and any thin stand-in): 429 / 529 / 5xx are transient; 4xx like
    400 (bad request) and 401 (auth) are not.

    The streaming API needs an extra signal. When an ``error`` SSE event arrives
    *mid-stream*, the SDK raises an ``APIStatusError`` whose ``status_code`` is
    the stream's HTTP status — **200**, since the stream opened fine before the
    error event — so the "overloaded" signal lives only in the parsed
    ``body["error"]["type"]``, not the status. So when the exception carries a
    body dict, a server-side transient body type (``overloaded_error`` /
    ``api_error``, see ``_TRANSIENT_ERROR_TYPES``) is treated as transient even
    on a 200; this promotes such an error before the status check rejects it.
    A client-error body type (``invalid_request_error`` / ``authentication_error``)
    carries no such promotion, so a genuine 4xx stays non-transient.

    With no HTTP status, retry **only** a genuine connection/timeout error.
    A synchronous client-side error raised before any network round-trip — e.g.
    the SDK's ``ValueError`` demanding streaming for a large ``max_tokens``, or
    any request-validation failure — is deterministic: retrying it just burns
    the budget on the same failure, so it must surface immediately.
    """
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_type = (body.get("error") or {}).get("type")
        if error_type in _TRANSIENT_ERROR_TYPES:
            return True

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
        max_continuations: int = 3,
        backoff_base: float = 1.0,
    ):
        if client is None:
            import anthropic  # lazy: keep the module import-safe.

            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._max_continuations = max_continuations
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

    @staticmethod
    def _message_text(message) -> str:
        """Join the text blocks of a Message into one string."""
        return "".join(
            block.text for block in message.content if block.type == "text"
        )

    @staticmethod
    def _trim_overlap(accumulated: str, continuation: str) -> str:
        """Drop the prefix of ``continuation`` that repeats the tail of ``accumulated``.

        A continuation may re-emit the trailing slice of the accumulated text (or
        re-open a ``===FILE===`` marker it already wrote), so a raw concatenation
        would duplicate content. Find the largest ``k`` where the last ``k`` chars
        of ``accumulated`` equal the first ``k`` chars of ``continuation`` and drop
        that overlap. The API strips trailing whitespace off the prefill assistant
        message, so the seam may not land exactly at the raw cut — this longest-
        overlap match tolerates that drift.
        """
        # Cap the search window: a re-emitted tail / re-opened marker is at most
        # a few hundred chars, so bounding this keeps it cheap even when
        # ``accumulated`` is a ~100KB truncated chunk with no overlap (an
        # unbounded scan there is O(n^2) in slice copies).
        max_k = min(len(accumulated), len(continuation), _MAX_OVERLAP_SCAN)
        for k in range(max_k, 0, -1):
            if accumulated[-k:] == continuation[:k]:
                return continuation[k:]
        return continuation

    def complete(self, prompt, *, temperature):
        messages = [{"role": "user", "content": prompt}]
        accumulated = ""
        # The initial call plus up to ``max_continuations`` continuations. A
        # response cut off at the token cap (``stop_reason == "max_tokens"``) is a
        # partial output, so rather than hand a downstream parser a truncated
        # artifact we re-issue the request with the accumulated partial appended
        # as a trailing ``assistant`` message (native prefill): the model
        # continues the same token stream instead of starting a fresh reply.
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

            # Still truncated: prefill the accumulated text and continue.
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": accumulated},
            ]

        # The continuation budget is exhausted and the output is still truncated.
        # Surface the clear, actionable error (orchestrator drops with logging)
        # rather than return a partial artifact.
        raise ValueError(
            f"generation response was truncated at max_tokens "
            f"({self._max_tokens}) and was still incomplete after "
            f"{self._max_continuations} continuation(s); the model hit the "
            "output cap before finishing. Raise max_tokens or shrink the "
            "requested output."
        )
