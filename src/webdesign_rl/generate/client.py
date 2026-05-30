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

from typing import Protocol, runtime_checkable

# Single generation model for all three stages (design decision #10). The
# canonical model list spells out ``claude-opus-4-8``; the SDK's ``Model`` literal
# also accepts ``claude-opus-4-6``, so this exact ID is valid to wire.
GENERATION_MODEL = "claude-opus-4-6"


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

    def __init__(self, client=None, model: str = GENERATION_MODEL, max_tokens: int = 8192):
        if client is None:
            import anthropic  # lazy: keep the module import-safe.

            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, prompt, *, temperature):
        message = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in message.content if block.type == "text"
        )
