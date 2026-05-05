"""``recordorai-install`` CLI entry point.

Two modes:

* No args → launch the Textual TUI wizard (default for ``pip install``
  users).
* ``--rpc`` → run as a JSON-RPC server over stdio (Sprint 2 — used by
  the Tauri front-end).
"""

from __future__ import annotations

import argparse
import json
import sys

from .version import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recordorai-install",
        description="RecordorAI installer + integration wizard",
    )
    parser.add_argument(
        "--version", action="store_true", help="Print the installer version and exit."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk through the wizard and build the plan, but don't apply any changes.",
    )
    parser.add_argument(
        "--detect",
        action="store_true",
        help=(
            "Print the detected environment as JSON and exit (useful for scripting / debugging)."
        ),
    )
    parser.add_argument(
        "--rpc",
        action="store_true",
        help=(
            "Run as a JSON-RPC server over stdio (used by the Tauri "
            "GUI in Sprint 2). No-op in v0.1."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"recordorai-install {__version__}")
        return 0

    if args.detect:
        from dataclasses import asdict

        from .core.detect import detect_environment

        env = detect_environment()
        print(json.dumps(asdict(env), indent=2, default=str))
        return 0

    if args.rpc:
        # Sprint 2 wires this to a JSON-RPC server. For Sprint 1 we
        # just print a clear message so the Tauri integration has a
        # contract to test against.
        print(
            "RPC mode is wired in Sprint 2; for now run without --rpc.",
            file=sys.stderr,
        )
        return 2

    # Default: launch the TUI wizard.
    from .tui.app import run

    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
