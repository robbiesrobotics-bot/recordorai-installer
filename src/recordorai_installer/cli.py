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
            "Run as a JSON-RPC 2.0 server over stdio. The Tauri front-end "
            "spawns this and talks to the same core the TUI uses."
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
        # JSON-RPC 2.0 over stdio — used by the Tauri front-end.
        from .rpc import run as rpc_run

        return rpc_run()

    # Default: launch the TUI wizard.
    from .tui.app import run

    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
