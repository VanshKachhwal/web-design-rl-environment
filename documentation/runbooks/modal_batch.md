# Running the generator batch on Modal

Operational runbook for the Modal batch runner
(`src/webdesign_rl/generate/modal_batch.py`, issue 06). It fans the per-site
gated pipeline out across the stratified seed list, runs each site **inside the
sealed render image** (same image used to grade), gates it, emits the survivors
as Harbor tasks, and reports the yield + per-check telemetry.

> Goal of this doc: get a clean Modal run end-to-end before scaling. Do the
> small smoke test first; only run the full batch once that works.

---

## 1. What the batch actually does (end to end)

1. **Builds one Modal image** from the *same* Dockerfile as the render/grade
   image (`render/container._RENDER_DOCKERFILE` + your package): `python:3.12-slim`
   + the OS-level font palette (DejaVu + the 9 curated families) + Playwright's
   Chromium + the `webdesign_rl` package. Modal builds this **once on its own
   cloud builder** and caches it. (Bonus: this runs on Modal's infra, so it
   sidesteps the local Docker Desktop / Playwright-CDN flakiness entirely.)
2. **Provisions a Volume** (`webdesign-rl-artifacts`, persistent cloud disk)
   mounted at `/artifacts` in every container, and injects your
   `ANTHROPIC_API_KEY` from a **Secret** (`anthropic-api-key`).
3. **Fans out the seeds**: `sample_seeds(N)` → `worker.map(enumerate(seeds))`,
   running up to **10 containers in parallel** (`DEFAULT_CONCURRENCY`, to stay
   under the single API key's rate limit). Each container runs **one seed's full
   gated pipeline**:
   - stage 1 → 2 → 3 LLM generation calls,
   - the quality gate (stage 4 deterministic + stage 5 render via the in-image
     Chromium — *not* nested Docker),
   - bounded repair (nudges),
   - on pass: emits the Harbor task (reference screenshots rendered in-image),
   - writes artifacts to the Volume and commits.
4. **Collects results and prints a report**: gate **yield** (e.g. `37/48 passed`)
   plus per-check telemetry (`drops_by_check`, `nudges_by_check`).

Per-container cloud resources are pinned: `cpu=2.0`, `memory=4096` (MB),
`timeout=1800` (30 min/seed). These are Modal-cloud resources — independent of
your laptop.

---

## 2. One-time setup

All commands use the project venv. The package is run from `src/` (not installed),
so keep `PYTHONPATH=src` for the Python entrypoints; the `modal` CLI lives at
`.venv/bin/modal` after install.

```bash
# 1. Install the Modal client into the venv
uv pip install modal                     # or: .venv/bin/pip install modal

# 2. Authenticate this machine to your Modal workspace (opens a browser)
.venv/bin/modal token new                # or: .venv/bin/modal setup

# 3. Create the Secret the batch reads the API key from.
#    The name MUST be exactly "anthropic-api-key" and it MUST expose the env var
#    ANTHROPIC_API_KEY (that's what AnthropicGenerationClient reads).
.venv/bin/modal secret create anthropic-api-key ANTHROPIC_API_KEY="sk-ant-..."

# If it says "Secret 'anthropic-api-key' already exists", it was created before.
# Either reuse it (verify with `modal secret list`) or overwrite to be certain
# the env-var name/value are right (a wrong var name = a confusing in-container
# auth error later, not a create-time error):
.venv/bin/modal secret create anthropic-api-key ANTHROPIC_API_KEY="sk-ant-..." --force
```

The Volume is created automatically on first run (`create_if_missing=True`) — you
don't provision it. To pre-create or inspect it:

```bash
.venv/bin/modal volume list
.venv/bin/modal volume create webdesign-rl-artifacts   # optional; auto-created otherwise
```

---

## 3. Running it

**Always smoke-test with a tiny batch first** — it exercises the whole path
(image build + secret + volume + one fan-out + emit + report) for ~4 sites:

```bash
PYTHONPATH=src .venv/bin/python -c \
  "from webdesign_rl.generate.modal_batch import run_batch; run_batch(4)"
```

The **full batch** (48 stratified seeds):

```bash
PYTHONPATH=src .venv/bin/python -m webdesign_rl.generate.modal_batch
```

`run_batch(count)` controls the seed count; the `python -m` entrypoint uses the
default 48. Change the count by calling `run_batch(N)` as in the smoke test.

> First run pays a one-time image build on Modal (Chromium + fonts). Subsequent
> runs reuse the cached image and start in seconds.

---

## 4. What you'll see while it runs

- **In your terminal**: Modal streams build logs, then per-container logs from the
  pipeline (`stage 1: …`, `gate: …`, `repair: nudging …`, `seed <id> passed/…`),
  then the final report block:
  ```
  batch: 37/48 passed (yield 77.1%); 11 dropped
    drops by check: substance=5, font_palette=3, ...
    nudges by check: token_compliance=14, substance=6, ...
  ```
- **On the Modal dashboard** (https://modal.com): an ephemeral app named
  `webdesign-rl-batch` appears while running — per-container status, resource
  usage, and full logs. Useful when a container is slow or errors.

---

## 5. Where the results are stored

Everything lands on the **Modal Volume `webdesign-rl-artifacts`** — cloud storage,
**not your laptop** — one directory per seed:

```
/artifacts/<seed_id>/site/    # gated HTML/CSS + page_map.json + seed.json
/artifacts/<seed_id>/task/    # the emitted Harbor task (survivors only)
```

`<seed_id>` is `"{index:03d}_{archetype}_{aesthetic}_{complexity}"`, e.g.
`000_saas-landing_swiss-editorial_low`. The index prefix makes the dirs sort in
batch order.

Note: the `SeedResult.task_dir` paths printed by the run are paths **inside the
container/volume** (`/artifacts/...`), so they don't exist on your machine until
you download them (next section).

---

## 6. Downloading the results

```bash
# Browse what's on the volume
.venv/bin/modal volume ls webdesign-rl-artifacts
.venv/bin/modal volume ls webdesign-rl-artifacts /000_saas-landing_swiss-editorial_low

# Download ONE seed's artifacts
.venv/bin/modal volume get webdesign-rl-artifacts \
  /000_saas-landing_swiss-editorial_low ./out/batch/

# Download EVERYTHING
.venv/bin/modal volume get webdesign-rl-artifacts / ./out/batch/
```

Then eyeball locally — open the rendered screenshots and the site:

```bash
open ./out/batch/000_*/task/             # the Harbor task (incl. reference PNGs)
open ./out/batch/000_*/site/index.html   # the generated site
```

(Reminder: judge typography on the *in-container* PNGs under `task/`, not a local
browser open of the HTML — your Mac lacks the bundled font palette.)

---

## 7. Cost & throughput notes

- **LLM cost**: ~12 Opus calls per site (stage 1 + stage 2 + one per page + any
  nudges). 4 sites ≈ ~50 calls; 48 sites ≈ ~600 calls. Start small.
- **Concurrency**: `DEFAULT_CONCURRENCY = 10` caps in-flight containers so the
  single API key doesn't get rate-limited (the client already retries/backs off
  429/529). Raise it for more throughput only if you also have rate-limit
  headroom; lower it if you see sustained 429s.
- **Per-seed resources**: `cpu=2.0`, `memory=4096 MB`, `timeout=1800s`. Sized for
  the in-image Chromium render. A seed exceeding 30 min is killed.
- These constants live at the top of `modal_batch.py` (`DEFAULT_CONCURRENCY`,
  `WORKER_CPU`, `WORKER_MEMORY_MB`) — tunable without touching logic.

---

## 8. Idempotency & re-runs

The Volume persists across runs. `run_one_seed` clears and rewrites **only that
seed's** `/artifacts/<seed_id>/` directory, so:

- A mid-batch failure doesn't lose the other seeds' artifacts.
- Re-running the batch overwrites each seed's dir fresh (same seeds → same ids).
- To wipe and start clean: `modal volume rm webdesign-rl-artifacts <path>` per
  entry, or delete the volume and let it auto-recreate.

---

## 9. Troubleshooting

- **`TypeError` on `Image.from_dockerfile(... context_dir=...)`** — the only
  Modal-version-specific call (in the untested wrapper `_build_modal_app`). Check
  `.venv/bin/modal --version`; if your version names the kwarg differently,
  adjust that one line. The `run_batch(4)` smoke test surfaces this immediately.
- **`Secret 'anthropic-api-key' not found`** — create it (step 2.3) with that
  exact name, exposing `ANTHROPIC_API_KEY`.
- **Auth / `not logged in`** — `.venv/bin/modal token new`.
- **Sustained 429s** in the logs — lower `DEFAULT_CONCURRENCY`; the client retries
  transient 429/529 automatically, so occasional ones are fine.
- **A seed times out (30 min)** — usually a stuck render or a pathological page;
  it surfaces as a failed container in the dashboard. Investigate that seed's logs.
- **First image build is slow** — expected (Chromium + fonts), one-time, cached
  after. This runs on Modal's builder, which is far more reliable than the local
  Docker Desktop Playwright-CDN path.
- **`ModuleNotFoundError: webdesign_rl` locally** — you forgot `PYTHONPATH=src` on
  the Python entrypoint (the package isn't pip-installed in the venv).

---

## 10. Key names (reference)

| Thing | Value | Where |
|---|---|---|
| Modal app | `webdesign-rl-batch` | `APP_NAME` |
| Volume | `webdesign-rl-artifacts` (mounted `/artifacts`) | `VOLUME_NAME` / `VOLUME_MOUNT` |
| Secret | `anthropic-api-key` → `ANTHROPIC_API_KEY` | `SECRET_NAME` |
| Batch size | 48 | `DEFAULT_BATCH_SIZE` |
| Concurrency | 10 containers | `DEFAULT_CONCURRENCY` |
| Per-seed CPU / RAM | 2.0 vCPU / 4096 MB | `WORKER_CPU` / `WORKER_MEMORY_MB` |
| Per-seed timeout | 30 min | `timeout` on `@app.function` |
| Artifact layout | `/artifacts/<seed_id>/{site,task}` | `run_one_seed` |

---

## 11. Definition of a successful run (before progressing)

- The image builds and the smoke test (`run_batch(4)`) prints a report with a
  non-zero yield.
- `modal volume get` pulls down at least one `<seed_id>/site/` + `<seed_id>/task/`.
- The downloaded `task/` screenshots look like coherent, multi-page sites.

Once that holds, run the full 48-seed batch and use the per-check telemetry to
decide gate tuning (e.g. whether to relax token-compliance) — then move on to
curation (issue 07).
