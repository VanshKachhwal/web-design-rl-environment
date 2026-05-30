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


def test_anthropic_client_is_import_safe_without_api_key():
    # Constructing with an injected fake client must not import/require the SDK
    # or a key — only an actual ``.complete`` call would touch the SDK.
    class _FakeMessages:
        def create(self, **kwargs):
            class _Block:
                type = "text"
                text = "<html></html>"

            class _Msg:
                content = [_Block()]

            return _Msg()

    class _FakeClient:
        messages = _FakeMessages()

    client = AnthropicGenerationClient(client=_FakeClient())
    out = client.complete("hi", temperature=0.6)
    assert out == "<html></html>"


def test_generation_model_id_is_opus_46():
    assert GENERATION_MODEL == "claude-opus-4-6"
