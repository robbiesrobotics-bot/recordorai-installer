"""``python -m recordorai_installer`` entry point.

Forwards to :func:`recordorai_installer.cli.main`.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
