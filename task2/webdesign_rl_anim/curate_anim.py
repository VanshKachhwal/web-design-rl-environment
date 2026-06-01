"""Lean curation: pick diverse survivors from a pulled animation batch.

Parity with Task 1's ``scripts/curate.py``: a pulled batch is
``<batch>/<seed_id>/{site,task}/``; a *survivor* is a seed dir carrying an emitted
``task/task.toml`` (a gate drop/error leaves only ``site/``). Curation keeps **one
survivor per ``(archetype, aesthetic)`` cell** and copies the **whole seed dir**
(``site/`` + ``task/``) into ``<out>/<seed_id>/`` — like Task 1, the raw generated
site is kept alongside the runnable task (provenance / inspection), not dropped.

The grader/eval then runs against the ``task/`` subdir of each curated entry.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def survivors(batch_dir):
    """Yield ``(seed_id, seed_dir, archetype, aesthetic)`` for each passed site.

    A survivor is a seed dir whose ``task/task.toml`` exists. Archetype/aesthetic
    come from the site's ``seed.json`` provenance (falling back to the seed_id name).
    """
    batch_dir = Path(batch_dir)
    for seed_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        if not (seed_dir / "task" / "task.toml").exists():
            continue
        archetype = aesthetic = "?"
        seed_json = seed_dir / "site" / "seed.json"
        if seed_json.exists():
            tup = json.loads(seed_json.read_text()).get("seed_tuple", [])
            archetype = tup[0] if len(tup) > 0 else "?"
            aesthetic = tup[1] if len(tup) > 1 else "?"
        yield seed_dir.name, seed_dir, archetype, aesthetic


def curate(batch_dir, out_dir, *, limit=None):
    """Copy one WHOLE seed dir per (archetype, aesthetic) cell into ``out_dir``.

    Returns the kept seed ids. Each ``<out>/<seed_id>/`` holds ``site/`` + ``task/``
    (same as Task 1) — the runnable Harbor task is ``<out>/<seed_id>/task/``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seen, kept = set(), []
    for seed_id, seed_dir, archetype, aesthetic in survivors(batch_dir):
        cell = (archetype, aesthetic)
        if cell in seen:
            continue
        seen.add(cell)
        dest = out_dir / seed_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(seed_dir, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        kept.append(seed_id)
        if limit and len(kept) >= limit:
            break
    return kept


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m webdesign_rl_anim.curate_anim")
    ap.add_argument("--batch", required=True, help="Pulled batch dir (<id>/{site,task}/).")
    ap.add_argument("--out", required=True, help="Where to write the curated seed dirs.")
    ap.add_argument("--limit", type=int, default=None, help="Max survivors to keep.")
    a = ap.parse_args(argv)
    kept = curate(a.batch, a.out, limit=a.limit)
    print(f"curated {len(kept)} task(s) -> {a.out}  (each holds site/ + task/)")
    for k in kept:
        print(f"  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
