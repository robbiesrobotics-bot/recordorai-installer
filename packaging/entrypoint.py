"""PyInstaller entry-point for the recordorai-install binary.

Re-exports :func:`recordorai_installer.cli.main`. Lives in the
packaging/ folder so it sits next to the .spec file PyInstaller
expects.

When the binary is launched without args it runs the TUI. With
``--rpc`` it runs the JSON-RPC stdio server (Sprint 2). With
``--detect`` / ``--version`` / ``--dry-run`` it does the documented
non-interactive things.
"""

from __future__ import annotations

import sys


def main() -> int:
    from recordorai_installer.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
