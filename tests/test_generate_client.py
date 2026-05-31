"""Behavioral tests for the thin, stubbable generation LLM client.

All three generation stages reach the model through one boundary — a client
with a single ``complete(prompt, *, temperature)`` method — mirroring the
grader's ``JudgeClient``. This is the seam that lets the deterministic pipeline
(prompt assembly, parsing, assembly into a site) run with no live API call. The
real Anthropic-backed client must stay import-safe (SDK imported lazily).
"""

from webdesign_rl.generate.client import (
    GENERATION_MODEL,
    AnthropicGenerationClient,
    StubGenerationClient,
)


def test_stub_returns_canned_response_per_prompt():
    stub = StubGenerationClient(responses=["first", "second"])
    assert stub.complete("p1", temperature=1.0) == "first"
    assert stub.complete("p2", temperature=0.7) == "second"


def test_stub_records_calls_with_temperature():
    stub = StubGenerationClient(responses=["x"])
    stub.complete("the-prompt", temperature=0.6)
    assert stub.calls == [("the-prompt", 0.6)]


class _StreamCtx:
    """Stand-in for the SDK's streaming context manager.

    The real client uses ``with messages.stream(...) as s: s.get_final_message()``
    (streaming is required for the large ``max_tokens`` cap), so the fakes expose
    a ``stream`` method returning this context manager rather than ``create``.
    """

    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._msg


def test_anthropic_client_is_import_safe_without_api_key():
    # Constructing with an injected fake client must not import/require the SDK
    # or a key — only an actual ``.complete`` call would touch the SDK.
    class _Block:
        type = "text"
        text = "<html></html>"

    class _Msg:
        content = [_Block()]
        stop_reason = "end_turn"

    class _FakeMessages:
        def stream(self, **kwargs):
            return _StreamCtx(_Msg())

    class _FakeClient:
        messages = _FakeMessages()

    client = AnthropicGenerationClient(client=_FakeClient())
    out = client.complete("hi", temperature=0.6)
    assert out == "<html></html>"


def test_generation_model_id_is_opus_46():
    assert GENERATION_MODEL == "claude-opus-4-6"


def _fake_anthropic(stop_reason="end_turn", text="ok"):
    """A minimal fake Anthropic client whose message carries a stop_reason."""
    class _Block:
        type = "text"

        def __init__(self, t):
            self.text = t

    class _Msg:
        def __init__(self):
            self.content = [_Block(text)]
            self.stop_reason = stop_reason

    class _Messages:
        def __init__(self):
            self.kwargs = None

        def stream(self, **kwargs):
            self.kwargs = kwargs
            return _StreamCtx(_Msg())

    class _Client:
        messages = _Messages()

    return _Client()


def test_truncated_response_raises_a_clear_error_not_a_silent_partial():
    # When the Messages API reports stop_reason == "max_tokens", the response was
    # cut off mid-output; the client must raise a clear, actionable error rather
    # than return a partial string a downstream parser will crash on.
    import pytest

    client = AnthropicGenerationClient(
        client=_fake_anthropic(stop_reason="max_tokens", text="===FILE variables")
    )
    with pytest.raises(ValueError) as exc:
        client.complete("hi", temperature=0.7)
    assert "max_tokens" in str(exc.value) or "truncat" in str(exc.value).lower()


def test_complete_returns_text_when_stop_reason_is_normal():
    client = AnthropicGenerationClient(
        client=_fake_anthropic(stop_reason="end_turn", text="<html></html>")
    )
    assert client.complete("hi", temperature=0.7) == "<html></html>"


class _Transient(Exception):
    """A stand-in for an SDK transient error, classified by status_code."""

    def __init__(self, status_code):
        super().__init__(f"transient {status_code}")
        self.status_code = status_code


class _NonTransient(Exception):
    """A stand-in for a non-retryable SDK error (e.g. auth / bad request)."""

    def __init__(self, status_code):
        super().__init__(f"non-transient {status_code}")
        self.status_code = status_code


def _flaky_anthropic(errors):
    """A fake client whose messages.stream raises the queued errors, then ok."""
    class _Block:
        type = "text"
        text = "ok"

    class _Msg:
        content = [_Block()]
        stop_reason = "end_turn"

    class _Messages:
        def __init__(self):
            self.queue = list(errors)
            self.attempts = 0

        def stream(self, **kwargs):
            self.attempts += 1
            if self.queue:
                raise self.queue.pop(0)
            return _StreamCtx(_Msg())

    class _Client:
        messages = _Messages()

    return _Client()


def test_transient_error_then_success_is_retried(monkeypatch):
    # A 429 then a 503 then success: the client retries (with backoff) and
    # ultimately returns the response, without a live API call.
    fake = _flaky_anthropic([_Transient(429), _Transient(503)])
    client = AnthropicGenerationClient(client=fake, max_retries=3, backoff_base=0)
    out = client.complete("hi", temperature=0.7)
    assert out == "ok"
    assert fake.messages.attempts == 3


def test_overloaded_error_is_retried():
    class _Overloaded(Exception):
        status_code = 529  # Anthropic 'overloaded_error'

    fake = _flaky_anthropic([_Overloaded()])
    client = AnthropicGenerationClient(client=fake, max_retries=2, backoff_base=0)
    assert client.complete("hi", temperature=0.7) == "ok"


def test_non_transient_error_is_not_retried():
    import pytest

    fake = _flaky_anthropic([_NonTransient(400)])
    client = AnthropicGenerationClient(client=fake, max_retries=3, backoff_base=0)
    with pytest.raises(_NonTransient):
        client.complete("hi", temperature=0.7)
    # Exactly one attempt — a bad request / auth failure must not be retried.
    assert fake.messages.attempts == 1


def test_status_less_client_side_error_is_not_retried():
    # A synchronous client-side error with no HTTP status_code (e.g. the SDK's
    # ValueError demanding streaming for a large max_tokens) is deterministic —
    # retrying it would just burn the budget on the identical failure. It must
    # surface immediately, unlike a real connection error (which has no status
    # but IS retried).
    import pytest

    fake = _flaky_anthropic([ValueError("Streaming is required ...")])
    client = AnthropicGenerationClient(client=fake, max_retries=3, backoff_base=0)
    with pytest.raises(ValueError):
        client.complete("hi", temperature=0.7)
    assert fake.messages.attempts == 1


def test_connection_error_with_no_status_is_retried():
    # A genuine connection/timeout error carries no status_code but is transient;
    # it must still be retried (the status-less path must not regress).
    fake = _flaky_anthropic([ConnectionError("connection reset"), TimeoutError("slow")])
    client = AnthropicGenerationClient(client=fake, max_retries=3, backoff_base=0)
    assert client.complete("hi", temperature=0.7) == "ok"
    assert fake.messages.attempts == 3


def test_transient_errors_beyond_budget_surface_the_error():
    import pytest

    fake = _flaky_anthropic([_Transient(503), _Transient(503), _Transient(503)])
    client = AnthropicGenerationClient(client=fake, max_retries=2, backoff_base=0)
    with pytest.raises(_Transient):
        client.complete("hi", temperature=0.7)
    # initial + 2 retries = 3 attempts, then it gives up.
    assert fake.messages.attempts == 3


def test_default_max_tokens_is_a_model_safe_value():
    # 32000 is claude-opus-4-6's output ceiling (no beta header needed); bumped
    # from 16384 after a med-complexity stage-2 run overflowed the lower cap. The
    # robust fix for output that still exceeds this is continuation (issue 15);
    # the default must remain at/below the model's known-good ceiling.
    fake = _fake_anthropic()
    client = AnthropicGenerationClient(client=fake)
    client.complete("hi", temperature=0.7)
    assert fake.messages.kwargs["max_tokens"] == 32000
