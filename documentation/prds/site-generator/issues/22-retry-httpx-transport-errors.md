# 22 — Retry raw httpx transport errors (mid-stream "Connection reset by peer")

Status: done (committed d54accb)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live Modal batch: seed
`009_restaurant-hospitality_glassmorphism_low` errored mid-stage-2 on
`httpx.ReadError: [Errno 104] Connection reset by peer` — a transient network
drop that should have been retried but wasn't. Complements issues 19 (survive
the failure) and 20 (retry streaming-overload SSE events); this retries the
remaining class — raw connection-level drops.

## Background (the exact mechanism)

Generation uses the streaming API
(`messages.stream().get_final_message()`). The crash arose while *iterating the
stream bytes* (`get_final_message` → `until_done` → `iter_bytes`), not while
opening the request. The anthropic SDK only wraps httpx errors into
`APIConnectionError` on the **request-send** path; an error thrown **mid-stream
iteration propagates raw** as an `httpx.ReadError`.

Walking `client._is_transient(httpx.ReadError(...))`:

- `.body` → `None`; `.status_code` → `None` (the stream opened with HTTP 200,
  then the connection dropped — there is no HTTP error status to classify on).
- not an `anthropic.APIConnectionError` (httpx errors mid-stream aren't wrapped).
- not a builtin `ConnectionError` / `TimeoutError` (httpx has its own hierarchy;
  `httpx.ReadError` → `NetworkError` → `TransportError` → `RequestError`).

→ `_is_transient` returns **False** → not retried → the exception propagates out
of the stage → the seed errors. Issue 19 isolated it (the batch survived), but a
recoverable blip *wasted* the seed and its LLM spend instead of riding it out.

Observed crash tail:
```
httpx.ReadError: [Errno 104] Connection reset by peer
```

## What to build (in `client._is_transient`)

Treat raw **`httpx.TransportError`** as transient (lazy import of `httpx`, the
same pattern as the lazy `anthropic` import already there).

- `httpx.TransportError` is the base of every connection-level failure worth a
  retry: `ConnectError`, `ReadError`, `WriteError`, the network timeouts
  (`ConnectTimeout` / `ReadTimeout` / `WriteTimeout` / `PoolTimeout`), and
  `RemoteProtocolError` (server disconnected). Classify any of these as transient.
- Do **not** broaden to `httpx.HTTPStatusError` (that carries a real HTTP status
  and is already handled by the `status_code` branch) nor to non-transport
  `RequestError`s. The SDK's streaming-required `ValueError` and other
  deterministic client-side errors must stay **non-transient** (unchanged).
- Keep every existing branch intact: transient error *body* types
  (`overloaded_error` / `api_error`) first; then 429 / 529 / 5xx by status;
  then `anthropic.APIConnectionError`; then builtin `ConnectionError` /
  `TimeoutError`. The new httpx check slots in alongside the connection-level
  classification.

On retry, `_create_message` opens a **fresh** stream (`messages.stream(...)`
from scratch), so a mid-stream drop cleanly restarts the stage call within the
existing `_create_with_retry` backoff loop.

## Acceptance criteria

- [ ] `_is_transient(httpx.ReadError(...))` is **True** (retried); same for
      `httpx.ConnectError`, `httpx.ReadTimeout`, and `httpx.RemoteProtocolError`.
- [ ] `_is_transient(httpx.HTTPStatusError)` with a 400-level response stays
      **False** (still classified by status, not blanket-retried); the SDK's
      streaming-required `ValueError` stays **False**.
- [ ] All existing classifications unchanged: `overloaded_error`/`api_error`
      body → transient; 429/529/5xx → transient; bare `ConnectionError` →
      transient; deterministic `ValueError` → not.
- [ ] A simulated **mid-stream `httpx.ReadError` then success** is exercised
      through the client: a fake whose first `stream()`/`get_final_message()`
      raises an `httpx.ReadError`, then succeeds → `complete()` retries (backoff)
      and returns the text. No live API call.
- [ ] `httpx` is imported lazily (module stays import-safe); full suite green
      (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None. Independent of issue 21. Touches only `generate/client._is_transient`
  (+ its tests). Complementary to 19 (survives failures) and 20 (retries
  streaming-overload SSE events).
