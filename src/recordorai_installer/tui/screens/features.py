"""Screen 4 — feature toggles + palace path."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Static

from ...core.license import LicenseState
from ..state import WizardState


class FeaturesScreen(Screen):
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
            yield Static("Features", classes="title")
            yield Static(
                "Pick what RecordorAI should ingest on this machine. "
                "You can re-run the installer later to enable more.",
                classes="subtitle",
            )
            yield Static("Palace root (where data lives):", classes="muted")
            yield Input(
                value=self.state.palace_root,
                placeholder="~/.recordorai",
                id="palace-input",
            )

            yield Static("Ingest types:", classes="title")
            yield Checkbox(
                "Documents (PDF, .docx, .pptx, .html)  —  small, recommended",
                value=self.state.enable_documents,
                id="cb-documents",
            )
            yield Checkbox(
                "Audio (voice memos via WhisperX, ~3 GB model)",
                value=self.state.enable_audio,
                id="cb-audio",
            )
            yield Checkbox(
                "Image (screenshots/photos via Qwen3-VL, ~3 GB model)",
                value=self.state.enable_image,
                id="cb-image",
            )
            yield Checkbox(
                "Video (mp4/mov via ffmpeg + audio + image)",
                value=self.state.enable_video,
                id="cb-video",
            )
            if self.state.env.host.is_apple_silicon:
                yield Checkbox(
                    "ANE-accelerated rerank (recommended for M-series)",
                    value=self.state.enable_rerank_ane,
                    id="cb-ane",
                )

            if self.state.edition == "pro" and self._pro_unlocked():
                yield Static("Pro features:", classes="title")
                yield Checkbox(
                    "Multi-tenant (per-user palaces with ACLs)",
                    value=self.state.enable_multi_tenant,
                    id="cb-multi-tenant",
                )
                yield Checkbox(
                    "Cross-device sync (encrypted)",
                    value=self.state.enable_sync,
                    id="cb-sync",
                )
                yield Checkbox(
                    "Smart Observer (LLM-augmented capsule generation)",
                    value=self.state.enable_smart_observer,
                    id="cb-smart-observer",
                )

        with Horizontal(id="wizard-footer"):
            yield Button("Back", id="back")
            yield Button("Continue", id="continue", classes="primary")

    def _pro_unlocked(self) -> bool:
        s = self.state.license_status
        return bool(s and s.state in (LicenseState.ACTIVE, LicenseState.GRACE))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        attr_map = {
            "cb-documents": "enable_documents",
            "cb-audio": "enable_audio",
            "cb-image": "enable_image",
            "cb-video": "enable_video",
            "cb-ane": "enable_rerank_ane",
            "cb-multi-tenant": "enable_multi_tenant",
            "cb-sync": "enable_sync",
            "cb-smart-observer": "enable_smart_observer",
        }
        attr = attr_map.get(event.checkbox.id or "")
        if attr is not None:
            setattr(self.state, attr, event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "continue":
            self.action_advance()

    def action_advance(self) -> None:
        from .review import ReviewScreen

        # Persist palace path edit.
        self.state.palace_root = self.query_one("#palace-input", Input).value
        self.app.push_screen(ReviewScreen(self.state))
