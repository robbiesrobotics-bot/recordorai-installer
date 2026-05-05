"""Screen 3 — pick the agent runtime to integrate with."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, RadioButton, RadioSet, Static

from ...adapters import get_adapter, supported_runtimes
from ..state import WizardState


class RuntimeScreen(Screen):
    BINDINGS = [
        ("enter", "advance", "Continue"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("RecordorAI Installer", id="wizard-header")
        with Vertical(id="wizard-body"):
            yield Static("Choose your runtime", classes="title")
            yield Static(
                "RecordorAI integrates with several agent runtimes. "
                "Pick the one you use most. You can always re-run the "
                "wizard later to add another.",
                classes="subtitle",
            )

            with RadioSet(id="runtime-set"):
                for name in supported_runtimes():
                    adapter = get_adapter(name)
                    eligible = adapter.is_eligible(self.state.env)
                    label = f"{adapter.label}"
                    if not eligible:
                        label += "  (not detected)"
                    yield RadioButton(
                        label,
                        value=self.state.runtime == name,
                        id=f"rt-{name.replace('-', '_')}",
                        disabled=not eligible,
                    )

            yield Static("", id="runtime-detail", classes="muted")

        with Horizontal(id="wizard-footer"):
            yield Button("Back", id="back")
            yield Button("Continue", id="continue", classes="primary")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        # rt-pi_mono → "pi-mono"
        rb_id = event.pressed.id or ""
        name = rb_id.removeprefix("rt-").replace("_", "-")
        self.state.runtime = name
        adapter = get_adapter(name)
        self.query_one("#runtime-detail", Static).update(adapter.description)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            self.action_advance()

    def action_advance(self) -> None:
        from .features import FeaturesScreen

        self.app.push_screen(FeaturesScreen(self.state))
