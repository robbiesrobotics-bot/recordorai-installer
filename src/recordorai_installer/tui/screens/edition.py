"""Screen 2 — Community vs Pro + (optional) license key entry."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, RadioButton, RadioSet, Static

from ..state import WizardState


class EditionScreen(Screen):
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
            yield Static("Edition", classes="title")
            yield Static(
                "Community is free forever. Pro adds multi-tenant, "
                "cross-device sync, and the smart Observer (LLM-augmented "
                "ingest enrichment). Pro is a monthly subscription.",
                classes="subtitle",
            )

            with RadioSet(id="edition-set"):
                yield RadioButton(
                    "Community  —  Free, all retrieval + all ingest types",
                    value=self.state.edition == "community",
                    id="ed-community",
                )
                yield RadioButton(
                    "Pro  —  $X/month, multi-tenant + sync + smart Observer",
                    value=self.state.edition == "pro",
                    id="ed-pro",
                )

            yield Static(
                "License key (Pro only — leave blank for Community):",
                classes="muted",
            )
            yield Input(
                placeholder="RAI-PRO-XXXX-XXXX-XXXX",
                id="license-input",
                value=self.state.license_key or "",
            )
            yield Static("", id="license-status")

        with Horizontal(id="wizard-footer"):
            yield Button("Back", id="back")
            yield Button("Validate Pro", id="validate")
            yield Button("Continue", id="continue", classes="primary")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.state.edition = "pro" if event.pressed.id == "ed-pro" else "community"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "validate":
            self._validate_now()
        elif event.button.id == "continue":
            self.action_advance()

    def _validate_now(self) -> None:
        from ...core.license import validate_online

        key = self.query_one("#license-input", Input).value.strip()
        if not key:
            self._set_status("(no key entered)", style="muted")
            return
        status = validate_online(key)
        self.state.license_key = key
        self.state.license_status = status
        self._set_status(
            f"{status.state.value}: {status.message}",
            style="ok" if status.state.value in ("active", "grace") else "error",
        )

    def _set_status(self, msg: str, *, style: str = "muted") -> None:
        widget = self.query_one("#license-status", Static)
        widget.update(msg)
        widget.set_classes([style])

    def action_advance(self) -> None:
        from .runtime import RuntimeScreen

        # If user picked Pro but didn't validate, give them one chance to.
        if self.state.edition == "pro" and self.state.license_status is None:
            self._validate_now()

        # If they picked Pro but the validation didn't go ACTIVE/GRACE,
        # downgrade to Community and warn — wizard never blocks; we
        # always let them install something.
        from ...core.license import LicenseState

        if (
            self.state.edition == "pro"
            and self.state.license_status is not None
            and self.state.license_status.state not in (LicenseState.ACTIVE, LicenseState.GRACE)
        ):
            self.state.edition = "community"
            self._set_status(
                "Pro features not unlocked — continuing as Community.",
                style="warn",
            )

        self.app.push_screen(RuntimeScreen(self.state))
