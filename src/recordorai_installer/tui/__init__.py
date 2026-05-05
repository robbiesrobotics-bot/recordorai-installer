"""Textual TUI wizard.

Entry point: :func:`recordorai_installer.tui.app.run`. The wizard
walks the user through 5 screens in order:

    1. Welcome / detection summary
    2. Edition (Community vs Pro + license key)
    3. Runtime picker (Standalone, OpenClaw, etc.)
    4. Features (audio / image / video / documents / etc.)
    5. Review + Install (executes the plan, streams progress)

State is held in a single :class:`recordorai_installer.tui.state.WizardState`
object that flows from screen to screen.
"""

from .app import run as run

__all__ = ["run"]
