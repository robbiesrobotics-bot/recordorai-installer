"""Screen 1 — welcome + detection summary.

Shows the user what we found on their machine (OS, Python, GPU,
detected runtimes, existing palace) and offers a single "Continue"
button. No input.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..state import WizardState


class WelcomeScreen(Screen):
    BINDINGS = [
        ("enter", "advance", "Continue"),
        ("escape", "app.quit", "Quit"),
    ]

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        from ...version import __version__, is_preview_build

        yield Static("RecordorAI Installer", id="wizard-header")
        with Vertical(id="wizard-body"):
            yield Static("Welcome", classes="title")

            # Pre-release banner — shown until v1.0 GA when builds
            # are signed + notarized. The user already saw the
            # OS-level warning on launch; this just explains it.
            if is_preview_build():
                yield Static(
                    f"Preview build {__version__} — installers are unsigned "
                    "while we wait on Apple Developer ID + Windows codesigning "
                    "paperwork. The OS-level warning you saw on launch is "
                    "expected. The Tauri auto-updater's Ed25519 signature is "
                    "always on, so future updates remain tamper-checked.",
                    classes="warn",
                    id="preview-banner",
                )

            yield Static(
                "We're going to set up RecordorAI on this machine. Here's what we found:",
                classes="subtitle",
            )
            yield Static(self._summary(), id="detection-summary")
            yield Static(
                "Press Enter to continue, or Ctrl+Q to quit.",
                classes="muted",
            )
        with Horizontal(id="wizard-footer"):
            yield Button("Continue", id="continue", classes="primary")
            yield Button("Quit", id="quit")

    def _summary(self) -> str:
        env = self.state.env
        lines = [
            f"OS:       {env.host.os} {env.host.os_version} ({env.host.arch})",
            f"Python:   {'.'.join(str(x) for x in env.python.version)} ({env.python.executable})",
        ]
        if env.host.is_apple_silicon:
            lines.append("GPU:      Apple Silicon — Neural Engine available")
        elif env.gpu.has_cuda:
            lines.append(f"GPU:      NVIDIA CUDA {env.gpu.cuda_version}")
        elif env.gpu.has_rocm:
            lines.append("GPU:      AMD ROCm")
        else:
            lines.append("GPU:      none detected (CPU-only — works fine for core)")

        detected = [r for r in env.runtimes if r.detected and r.name != "standalone"]
        if detected:
            lines.append("")
            lines.append("Agent runtimes detected:")
            for r in detected:
                ver = f" v{r.version}" if r.version else ""
                lines.append(f"  - {r.label if hasattr(r, 'label') else r.name}{ver}")
        else:
            lines.append("")
            lines.append("Agent runtimes: none detected (Standalone install path).")

        if self.state.env.existing_recordorai:
            lines.append("")
            lines.append(
                f"Existing RecordorAI {self.state.env.existing_recordorai} found "
                f"— this is an upgrade install."
            )
        if self.state.env.palace_root:
            lines.append(f"Palace root:  {self.state.env.palace_root}")

        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.action_advance()
        elif event.button.id == "quit":
            self.app.exit()

    def action_advance(self) -> None:
        from .edition import EditionScreen

        self.app.push_screen(EditionScreen(self.state))
