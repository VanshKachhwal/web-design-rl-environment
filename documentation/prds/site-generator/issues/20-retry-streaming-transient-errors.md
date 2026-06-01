# 20 — Retry streaming transient errors (overloaded_error on an HTTP-200 stream)

Status: done (committed 8b4c8d4)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Surfaced by the live Modal batch, which
crashed on a transient Anthropic **"Overloaded"** that should have been retried
but wasn't.

## Background (the exact mechanism)

The client retries transient errors (429 / 529 / 5xx) classified by HTTP
`status_code` in `client._is_transient`. But generation uses the **streaming**
API (`messages.stream().get_final_message()`), and the SDK raises a streaming
error differently (`anthropic/_streaming.py`): when an `error` SSE event arrives
**mid-stream**, it raises

```python
raise self._client._make_status_error(err_msg, body=body, response=self.response)
```

The stream's HTTP response was **200** (the stream opened fine, *then* an error
event came through), so the resulting `APIStatusError` has **`.status_code == 200`**
— the "overloaded" signal lives only in the parsed body
(`{'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}`),
**not** the HTTP status. So `_is_transient` sees `200` → "not transient" →
re-raises immediately, no retry → the exception propagates out of the seed
(crashing the run; see also issue 19 for batch isolation).

Observed crash tail:
```
anthropic.APIStatusError: {'type': 'error', 'error': {'type': 'overloaded_error',
'message': 'Overloaded'}, ...}
```

## What to build (in `client._is_transient`)

Classify a streaming transient error by its **error body type**, not just the
HTTP status:

- If the exception carries a parsed body dict (`getattr(exc, "body", None)` is a
  dict), read `body["error"]["type"]`; treat the **server-side transient** types
  — `overloaded_error` and `api_error` — as transient (retry with backoff). (A
  `rate_limit_error` normally arrives as a 429 HTTP status and is already covered;
  4xx client-error types like `invalid_request_error` / `authentication_error`
  must stay non-transient.)
- Keep the existing classification intact: 429 / 529 / 5xx by `status_code` →
  transient; other 4xx → not; no-`status_code` connection/timeout errors →
  transient; a deterministic client-side error (e.g. the SDK's streaming-required
  `ValueError`) → not.
- Restructure so a `status_code == 200` exception **with** a transient error body
  is retried, while a plain 4xx (e.g. 400, no transient body) is still not.

This lets the existing `_create_with_retry` backoff loop ride out a transient
overload (re-opening a fresh stream on each attempt) instead of crashing.

## Acceptance criteria

- [x] An exception with `status_code == 200` and body
      `{'error': {'type': 'overloaded_error'}}` → `_is_transient` is **True**
      (retried); same for `api_error`.
- [x] A `status_code == 400` error with no transient body → `_is_transient`
      **False** (still not retried).
- [x] 429 / 529 / 5xx → transient; a no-status connection error → transient; a
      no-status deterministic `ValueError` → not — all unchanged (existing tests
      stay green).
- [x] A simulated **streaming overload then success** is exercised through the
      client: a fake whose first `stream()`/`get_final_message()` raises a
      status-200 + `overloaded_error`-body error, then succeeds → `complete()`
      retries (backoff) and returns the text. No live API call.
- [x] Full suite green (clean `TMPDIR`, Docker render test excluded).

## Blocked by

- None. Complementary to issue 19: this **reduces** transient failures (retries
  the overload); issue 19 **survives** any that remain (errored SeedResult, no
  batch abort).
