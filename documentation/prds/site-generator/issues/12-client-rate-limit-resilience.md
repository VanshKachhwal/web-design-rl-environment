# 12 — Generation client rate-limit resilience (retry/backoff)

Status: done (committed 24b9a0a)

## Parent

PRD: `.scratch/site-generator/PRD.md`. Raised re: the 48-site batch on a single API key.

## What to build

`AnthropicGenerationClient` makes a single call with no retry, so a transient 429
(rate-limit), 5xx, or `overloaded_error` aborts the whole run. Add **retry with
exponential backoff** on those transient errors (the Anthropic SDK supports `max_retries`
and surfaces typed errors — use it and/or a thin wrapper). This hardens every run and is
the client-level half of surviving the batch on one key.

**Scope note:** the *per-batch concurrency cap* (throttling how many sites run at once so
48 × ~10 calls don't burst past the account RPM/TPM limits) is **already in issue 06**
(Modal batch runner) acceptance criteria — it stays there. This issue is only the
**client-level retry/backoff**, which composes with that throttle.

## Acceptance criteria

- [ ] The client retries transient errors (429 / 5xx / overloaded) with exponential
      backoff, then surfaces a clear error if still failing.
- [ ] A stubbed transient-error-then-success test confirms it retries and succeeds without
      a live API call.
- [ ] Non-transient errors (e.g. auth, bad request) are NOT retried.
- [ ] Full suite green.

## Blocked by

- None — can start immediately. (Batch concurrency capping remains issue 06.)
