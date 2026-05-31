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


# --- issue 20: streaming overloaded_error on an HTTP-200 stream -------------


class _StreamBodyError(Exception):
    """A stand-in for the SDK's streaming ``APIStatusError``.

    When an ``error`` SSE event arrives mid-stream the SDK raises a status error
    whose ``status_code`` is the *stream's* HTTP status (200, since the stream
    opened fine) — the real signal is only in the parsed ``body`` dict.
    """

    def __init__(self, status_code, body):
        super().__init__(str(body))
        self.status_code = status_code
        self.body = body


def _overloaded_body(error_type="overloaded_error"):
    return {"type": "error", "error": {"type": error_type, "message": "Overloaded"}}


def test_streaming_overloaded_body_on_200_is_transient():
    from webdesign_rl.generate.client import _is_transient

    exc = _StreamBodyError(200, _overloaded_body("overloaded_error"))
    assert _is_transient(exc) is True


def test_streaming_api_error_body_on_200_is_transient():
    from webdesign_rl.generate.client import _is_transient

    exc = _StreamBodyError(200, _overloaded_body("api_error"))
    assert _is_transient(exc) is True


def test_400_with_no_transient_body_is_not_transient():
    from webdesign_rl.generate.client import _is_transient

    # A genuine bad request: 4xx status and a client-error body type must stay
    # non-transient even though it carries a body dict.
    exc = _StreamBodyError(400, _overloaded_body("invalid_request_error"))
    assert _is_transient(exc) is False
    # And a 400 with no body at all is still not transient.
    assert _is_transient(_NonTransient(400)) is False


def test_streaming_overload_then_success_is_retried():
    # The end-to-end path: the first stream() raises a status-200 +
    # overloaded_error-body error (as the SDK does for an in-stream error event),
    # then the next attempt succeeds. The client must ride it out and return text.
    fake = _flaky_anthropic([_StreamBodyError(200, _overloaded_body("overloaded_error"))])
    client = AnthropicGenerationClient(client=fake, max_retries=2, backoff_base=0)
    assert client.complete("hi", temperature=0.7) == "ok"
    assert fake.messages.attempts == 2


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


# --- issue 15: continuation-on-truncation -----------------------------------


def _continuing_anthropic(segments):
    """A fake client that simulates a truncated-then-continued exchange.

    ``segments`` is a list of ``(text, stop_reason)`` pairs returned in order,
    one per underlying ``stream`` call. The fake records the ``messages`` of every
    call so a test can assert the assistant-prefill is sent on continuation. It
    also strips trailing whitespace off the prefilled assistant content — exactly
    as the live API does — so the seam guard is exercised under realistic input.
    """
    class _Block:
        type = "text"

        def __init__(self, t):
            self.text = t

    class _Msg:
        def __init__(self, text, stop_reason):
            self.content = [_Block(text)]
            self.stop_reason = stop_reason

    class _Messages:
        def __init__(self):
            self.queue = list(segments)
            self.calls = []  # the ``messages`` arg of each stream() call

        def stream(self, **kwargs):
            msgs = kwargs["messages"]
            # Mimic the API stripping trailing whitespace on a prefill assistant
            # message, so the resumed token stream may not abut the raw cut.
            if msgs and msgs[-1]["role"] == "assistant":
                msgs[-1]["content"] = msgs[-1]["content"].rstrip()
            self.calls.append(msgs)
            text, stop_reason = self.queue.pop(0)
            return _StreamCtx(_Msg(text, stop_reason))

    class _Client:
        messages = _Messages()

    return _Client()


def _good_design_system():
    """A known-good four-block stage-2 response the parser accepts."""
    from textwrap import dedent

    return dedent(
        """\
        ===FILE variables.css===
        :root { --brand: #0af; --ink: #111; --bg: #fff; }
        ===FILE components.css===
        .btn { color: var(--brand); padding: 8px 16px; border-radius: 6px; }
        .card { background: var(--bg); box-shadow: 0 2px 8px rgba(0,0,0,.1); }
        .nav { display: flex; gap: 24px; align-items: center; }
        ===FILE header.html===
        <header><nav class="nav"><a href="/">Home</a></nav></header>
        ===FILE footer.html===
        <footer><p>&copy; 2026 Example</p></footer>"""
    )


def test_truncated_then_continued_round_trips_through_parser():
    from webdesign_rl.generate.stages import parse_design_system

    full = _good_design_system()
    # Cut mid-components.css, at an arbitrary index inside the CSS body.
    cut = full.index("box-shadow") + 5
    head, tail = full[:cut], full[cut:]

    fake = _continuing_anthropic([(head, "max_tokens"), (tail, "end_turn")])
    client = AnthropicGenerationClient(client=fake, backoff_base=0)
    joined = client.complete("stage2 prompt", temperature=0.7)

    # The joined text reconstructs the exact original (the seam is invisible).
    ds = parse_design_system(joined)
    expected = parse_design_system(full)
    assert ds == expected
    # Exactly two underlying calls: the initial + one continuation.
    assert len(fake.messages.calls) == 2


def test_continuation_sends_assistant_prefill_with_accumulated_text():
    full = _good_design_system()
    cut = full.index("box-shadow") + 5
    head, tail = full[:cut], full[cut:]

    fake = _continuing_anthropic([(head, "max_tokens"), (tail, "end_turn")])
    client = AnthropicGenerationClient(client=fake, backoff_base=0)
    client.complete("stage2 prompt", temperature=0.7)

    first_call, second_call = fake.messages.calls
    # First call is the plain user prompt, no assistant turn.
    assert first_call[0]["role"] == "user"
    assert all(m["role"] != "assistant" for m in first_call)
    # The continuation appends the accumulated partial as a trailing assistant
    # message (the user prompt stays first).
    assert second_call[0]["role"] == "user"
    assert second_call[-1]["role"] == "assistant"
    assert second_call[-1]["content"] == head.rstrip()


def test_continuation_overlap_is_trimmed_not_doubled():
    from webdesign_rl.generate.stages import parse_design_system

    full = _good_design_system()
    cut = full.index("box-shadow") + 5
    head, tail = full[:cut], full[cut:]
    # The model repeats the tail of the accumulated text at the seam: prepend
    # the last 20 chars of ``head`` to the continuation.
    overlap = head[-20:]
    dup_tail = overlap + tail

    fake = _continuing_anthropic([(head, "max_tokens"), (dup_tail, "end_turn")])
    client = AnthropicGenerationClient(client=fake, backoff_base=0)
    joined = client.complete("stage2 prompt", temperature=0.7)

    # The overlap is trimmed, so the joined text equals the original — no doubled
    # marker / repeated CSS — and parses to the same design system.
    assert parse_design_system(joined) == parse_design_system(full)


def test_continuation_tolerates_whitespace_stripped_at_the_seam():
    from webdesign_rl.generate.stages import parse_design_system

    full = _good_design_system()
    # Cut at a newline boundary so the accumulated text ends in whitespace the
    # API strips off the prefill; the continuation resumes from the raw cut, so
    # the seam guard must still rejoin them without dropping the newline.
    cut = full.index("\n===FILE components.css===") + 1
    head, tail = full[:cut], full[cut:]
    assert head.endswith("\n")

    fake = _continuing_anthropic([(head, "max_tokens"), (tail, "end_turn")])
    client = AnthropicGenerationClient(client=fake, backoff_base=0)
    joined = client.complete("stage2 prompt", temperature=0.7)
    assert parse_design_system(joined) == parse_design_system(full)


def test_continuation_loop_is_bounded_then_raises_max_tokens_error():
    import pytest

    # Every segment is truncated: after the continuation budget is exhausted the
    # client raises the existing actionable max_tokens error (drop-with-logging),
    # never returns a partial artifact.
    budget = 2
    segments = [("===FILE variables", "max_tokens")] * (budget + 5)
    fake = _continuing_anthropic(segments)
    client = AnthropicGenerationClient(
        client=fake, backoff_base=0, max_continuations=budget
    )
    with pytest.raises(ValueError) as exc:
        client.complete("hi", temperature=0.7)
    msg = str(exc.value).lower()
    assert "max_tokens" in msg or "truncat" in msg
    # initial call + ``budget`` continuations = budget + 1 calls, then it gives up.
    assert len(fake.messages.calls) == budget + 1


def test_normal_single_shot_makes_no_extra_calls():
    fake = _continuing_anthropic([("<html></html>", "end_turn")])
    client = AnthropicGenerationClient(client=fake, backoff_base=0)
    assert client.complete("hi", temperature=0.7) == "<html></html>"
    assert len(fake.messages.calls) == 1


# --- issue 22: raw httpx transport errors (mid-stream "Connection reset") ----


def test_httpx_read_error_mid_stream_is_transient():
    # The crash that motivated this issue: a connection drop while iterating the
    # stream bytes propagates raw as ``httpx.ReadError`` (the SDK only wraps
    # httpx errors on the request-send path). It has no status_code and no body,
    # so it must be classified transient via the httpx-transport branch.
    import httpx

    from webdesign_rl.generate.client import _is_transient

    assert _is_transient(httpx.ReadError("[Errno 104] Connection reset by peer")) is True


def test_httpx_connection_level_errors_are_all_transient():
    # Every connection-level failure under ``TransportError`` is retryable: a
    # refused connect, a network timeout, and a server-side disconnect.
    import httpx

    from webdesign_rl.generate.client import _is_transient

    assert _is_transient(httpx.ConnectError("connection refused")) is True
    assert _is_transient(httpx.ReadTimeout("read timed out")) is True
    assert _is_transient(httpx.RemoteProtocolError("server disconnected")) is True


def test_httpx_status_error_400_is_not_transient():
    # An ``HTTPStatusError`` carries a real HTTP status (here 400) and is NOT a
    # ``TransportError`` — it must stay non-transient and not be blanket-retried
    # by the new httpx branch.
    import httpx

    from webdesign_rl.generate.client import _is_transient

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)
    exc = httpx.HTTPStatusError("bad request", request=request, response=response)
    assert _is_transient(exc) is False


def test_streaming_required_value_error_stays_non_transient():
    # The SDK raises a plain ``ValueError`` when a non-streaming request's
    # max_tokens could exceed 10 minutes ("Streaming is required ..."). It is a
    # deterministic client-side error with no status and is not an httpx
    # transport error, so retrying would just burn budget — it must stay False.
    from webdesign_rl.generate.client import _is_transient

    assert _is_transient(ValueError("Streaming is required for ...")) is False


def test_mid_stream_read_error_then_success_is_retried():
    # End-to-end: the first stream() raises a raw httpx.ReadError (as a connection
    # drop mid-iteration would), the next attempt succeeds. The client must ride
    # it out with backoff and return the text — no live API call, no real sleep
    # (backoff_base=0).
    import httpx

    fake = _flaky_anthropic([httpx.ReadError("[Errno 104] Connection reset by peer")])
    client = AnthropicGenerationClient(client=fake, max_retries=2, backoff_base=0)
    assert client.complete("hi", temperature=0.7) == "ok"
    assert fake.messages.attempts == 2
