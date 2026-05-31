"""CLI: pull generated artifacts off a Modal volume into a local dir (issue 26).

The command form of the documented
``modal volume get webdesign-rl-artifacts / ./out/batch/``. It downloads
**everything** on the volume — every ``<seed_id>/{site,task}`` dir, gate drops
(``site/`` only) included — faithfully mirroring the volume; survivor filtering
happens downstream in ``curate``. The resulting ``out/<volume>/<seed_id>/{site,task}``
layout is curate-compatible (``curate --batch out/<volume>``) with no massaging.

Same split as ``modal_batch`` / the eval launcher: a **pure, unit-tested core**
(:func:`build_pull_argv`, the exact ``modal volume get`` argv) and a **thin shell**
(:func:`main`) that ensures the dest exists and ``subprocess``-shells out to the
``modal`` CLI. The shell is the untested seam (``# pragma: no cover``).

The module is import-safe without ``modal``: nothing at top imports it; the shell
invokes the ``modal`` *CLI*, never the python package. ``--help`` renders anywhere.

Auth is Modal token auth only (``modal token new``) — no Anthropic key / Secret /
``.env``.

Run::

    PYTHONPATH=src .venv/bin/python scripts/pull_artifacts.py --volume webdesign-rl-artifacts
    PYTHONPATH=src .venv/bin/python scripts/pull_artifacts.py --volume batch-a --out out/batch-a --force -e prod
"""


def build_pull_argv(volume, dest, *, force=False, env=None):
    """Build the exact ``modal volume get`` argv to mirror a volume to ``dest``.

    Pure: no Modal, no I/O. Returns
    ``["modal", "volume", "get", volume, "/", str(dest)]`` (folders download
    recursively, so ``/`` pulls the whole volume), then — in a stable order —
    appends ``"--force"`` when ``force`` (overwrite existing files) and
    ``["-e", env]`` when an ``env`` (Modal environment) is given. ``dest`` is
    ``str()``- d so a ``Path`` is accepted.
    """
    argv = ["modal", "volume", "get", volume, "/", str(dest)]
    if force:
        argv.append("--force")
    if env is not None:
        argv += ["-e", env]
    return argv


# ---------------------------------------------------------------------------
# Thin shell — NOT unit-tested. ``subprocess``/``modal`` are exercised only in a
# live pull, exactly like ``modal_batch``'s lazy Modal wrapper. Imports are kept
# inside ``main`` so importing this module to get ``build_pull_argv`` stays
# side-effect-free and modal-free.
# ---------------------------------------------------------------------------


def main(argv=None):  # pragma: no cover - the untested subprocess/modal shell.
    import argparse
    import subprocess
    import sys
    from pathlib import Path

    from webdesign_rl.generate.modal_batch import VOLUME_NAME

    parser = argparse.ArgumentParser(
        description="Download a Modal volume of generated artifacts to a local dir.",
    )
    parser.add_argument(
        "--volume", default=VOLUME_NAME,
        help=f"Modal volume to pull (default: {VOLUME_NAME}).",
    )
    parser.add_argument(
        "--out", default=None,
        help="Destination dir (default: out/<volume>). Overrides the derived path.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing local files (modal volume get --force). Default off.",
    )
    parser.add_argument(
        "-e", "--env", default=None,
        help="Modal environment to pull from (default: workspace default).",
    )
    args = parser.parse_args(argv)

    out = Path(args.out) if args.out is not None else Path("out") / args.volume
    out.mkdir(parents=True, exist_ok=True)

    cmd = build_pull_argv(args.volume, out, force=args.force, env=args.env)
    print(f"Pulling {args.volume} -> {out} ...", file=sys.stderr)
    subprocess.run(cmd, check=True)
    print(out)
    return out


if __name__ == "__main__":  # pragma: no cover
    main()
