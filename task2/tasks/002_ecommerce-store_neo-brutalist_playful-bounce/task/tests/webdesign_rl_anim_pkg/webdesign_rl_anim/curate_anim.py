"""Lean curation: pick diverse survivors from a pulled animation batch.

A batch (pulled from the Modal volume to local) is ``<batch>/<seed_id>/{site,task}/``.
A *survivor* is a seed dir with an emitted ``task/`` (it passed the lean gate).
Curation keeps **one survivor per ``(archetype, aesthetic)`` cell** (read from the
site's ``seed.json`` provenance) so the final set spans site types/looks, and copies
each kept task to ``<out>/<seed_id>/`` (a ready-to-grade Harbor task dir).
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def survivors(batch_dir):
    """Yield ``(seed_id, task_dir, archetype, aesthetic)`` for each passed site."""
    batch_dir = Path(batch_dir)
    for seed_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        task_dir = seed_dir / "task"
        seed_json = seed_dir / "site" / "seed.json"
        if not (task_dir / "task.toml").exists() or not seed_json.exists():
            continue
        tup = json.loads(seed_json.read_text()).get("seed_tuple", [])
        archetype = tup[0] if len(tup) > 0 else "?"
        aesthetic = tup[1] if len(tup) > 1 else "?"
        yield seed_dir.name, task_dir, archetype, aesthetic


def curate(batch_dir, out_dir, *, limit=None):
    """Copy one task per (archetype, aesthetic) cell into ``out_dir``; return kept ids."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seen, kept = set(), []
    for seed_id, task_dir, archetype, aesthetic in survivors(batch_dir):
        cell = (archetype, aesthetic)
        if cell in seen:
            continue
        seen.add(cell)
        dest = out_dir / seed_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(task_dir, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        kept.append(seed_id)
        if limit and len(kept) >= limit:
            break
    return kept


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m webdesign_rl_anim.curate_anim")
    ap.add_argument("--batch", required=True, help="Pulled batch dir (<id>/{site,task}/).")
    ap.add_argument("--out", required=True, help="Where to write the curated task dirs.")
    ap.add_argument("--limit", type=int, default=None, help="Max tasks to keep.")
    a = ap.parse_args(argv)
    kept = curate(a.batch, a.out, limit=a.limit)
    print(f"curated {len(kept)} task(s) -> {a.out}")
    for k in kept:
        print(f"  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
