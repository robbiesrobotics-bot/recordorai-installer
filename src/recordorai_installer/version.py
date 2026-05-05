"""Single source of truth for the installer's version string.

Bumped manually for now; CI reads this on tag pushes via the
release.yml workflow (Sprint 4).

Pre-release suffixes follow PEP 440:

    0.1.0          → GA release
    0.1.0rc1       → release candidate
    0.1.0a1        → alpha
    0.1.0b1        → beta
    0.1.0.dev1     → in-development snapshot

The wizard's :func:`is_preview_build` reads this string to decide
whether to show the "early access — unsigned binaries" banner on
the Welcome screen.
"""

__version__ = "0.1.0rc1"


def is_preview_build() -> bool:
    """True iff the running version is anything other than a clean
    GA release. Used by the TUI Welcome screen and the Tauri
    front-end to surface a one-time "preview build" banner that
    explains the unsigned binary warnings.
    """
    return any(marker in __version__ for marker in ("a", "b", "rc", "dev"))
