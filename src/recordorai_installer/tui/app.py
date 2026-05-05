"""Textual App entry — wires the 5 screens together.

The wizard is keyboard-friendly first (Tab / Shift-Tab to navigate,
Enter to advance) and mouse-aware second. Every screen accepts
``WizardState`` and produces an updated copy on submit.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from ..core.detect import detect_environment
from .screens.welcome import WelcomeScreen
from .state import WizardState


class RecordorAIInstaller(App):
    """Textual app — 5 screens of wizard, then progress UI."""

    CSS_PATH = "app.tcss"
    TITLE = "RecordorAI Installer"
    SUB_TITLE = "Local-first AI memory"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, *, dry_run: bool = False) -> None:
        """
        Parameters
        ----------
        dry_run:
            When True, the wizard builds the plan and shows the review
            screen but does NOT execute any side effects. Used by
            ``recordorai-install --dry-run`` and by tests.
        """
        super().__init__()
        self.dry_run = dry_run
        self.state: WizardState | None = None

    def on_mount(self) -> None:
        env = detect_environment()
        self.state = WizardState(env=env)
        self.push_screen(WelcomeScreen(self.state))


def run(*, dry_run: bool = False) -> int:
    """Run the wizard. Returns the exit code (0 on success)."""
    app = RecordorAIInstaller(dry_run=dry_run)
    app.run()
    return 0
