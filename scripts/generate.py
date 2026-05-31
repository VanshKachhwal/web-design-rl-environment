"""CLI: kick off a Modal batch generation over the stratified seed list.

A thin argparse shell over :func:`webdesign_rl.generate.modal_batch.run_batch` —
the command form of ``python -m webdesign_rl.generate.modal_batch`` — exposing
``--count``, ``--concurrency``, and ``--volume`` (the latter two threaded into the
lazily-built Modal app). ``run_batch`` overgenerates ``--count`` seeds on Modal,
gates them in the sealed render image, emits survivors as Harbor tasks onto the
named ``Volume``, and prints the ``BatchReport`` (this CLI adds no report file).

This is the live-cloud, human-in-the-loop step: it relies on **Modal token auth**
(``modal token new``) **+ the ``anthropic-api-key`` Secret** — not ``.env``. The
module stays import-safe without ``modal`` installed (``run_batch`` defers all
Modal imports), so ``--help`` renders anywhere.

Run::

    PYTHONPATH=src .venv/bin/python scripts/generate.py \
        --count 48 --concurrency 10 --volume webdesign-rl-artifacts
"""

import argparse
import sys

from webdesign_rl.generate.modal_batch import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONCURRENCY,
    VOLUME_NAME,
    run_batch,
)


def main(argv=None):  # pragma: no cover - live-cloud HITL shell.
    parser = argparse.ArgumentParser(
        description="Kick off a Modal batch generation over the stratified seeds.",
    )
    parser.add_argument(
        "--count", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Number of seeds to overgenerate + gate. Default {DEFAULT_BATCH_SIZE}.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help="Max in-flight Modal worker containers. "
             f"Default {DEFAULT_CONCURRENCY}.",
    )
    parser.add_argument(
        "--volume", default=VOLUME_NAME,
        help=f"Artifact Volume name. Default {VOLUME_NAME}.",
    )
    args = parser.parse_args(argv)

    run_batch(count=args.count, concurrency=args.concurrency, volume=args.volume)


if __name__ == "__main__":  # pragma: no cover - the HITL live-cloud entrypoint.
    sys.exit(main())
