"""Screen 5 — review the plan, then install."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Log, Static

from ...core.exec_ import EventType, ExecEvent, execute
from ...core.plan import build_plan
from ..state import WizardState


class ReviewScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+i", "install", "Install"),
    ]

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        self.plan = build_plan(self.state.env, self.state.to_choices())
        self.state.plan_summary = self.plan.summary

    def compose(self) -> ComposeResult:
        yield Static("RecordorAI Installer", id="wizard-header")
        with Vertical(id="wizard-body"):
            yield Static("Review", classes="title")
            yield Static(self.plan.summary, classes="subtitle")
            yield Static("Steps to run:", classes="title")
            yield Static(self._steps_text(), id="steps-list")
            yield Log(id="progress-log")

        with Horizontal(id="wizard-footer"):
            yield Button("Back", id="back")
            yield Button("Install", id="install", classes="primary")
            yield Button("Quit", id="quit")

    def _steps_text(self) -> str:
        lines = []
        for i, step in enumerate(self.plan.steps, start=1):
            lines.append(f"{i:>2}. [{step.kind:<8}] {step.title}")
        return "\n".join(lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "install":
            self.action_install()
        elif event.button.id == "quit":
            self.app.exit()

    def action_install(self) -> None:
        log_widget = self.query_one("#progress-log", Log)
        log_widget.clear()

        if self.app.dry_run:
            log_widget.write("(dry-run mode — no side effects will occur)\n")

        def on_event(ev: ExecEvent) -> None:
            log_widget.write(self._format_event(ev) + "\n")

        # Run the plan synchronously — Sprint 1 keeps it simple.
        # Sprint 2's Tauri front-end uses execute_streaming via a
        # worker thread for true async UI.
        if not self.app.dry_run:
            result = execute(self.plan, on_event=on_event, allow_warn=False)
            if result.success:
                log_widget.write("\n[OK] RecordorAI installed successfully.\n")
            else:
                log_widget.write(f"\n[FAIL] Install rolled back. Error: {result.error}\n")

    def _format_event(self, ev: ExecEvent) -> str:
        if ev.type == EventType.STEP_START:
            return f"[{ev.index + 1}/{ev.total}] {ev.step.title}..."
        if ev.type == EventType.STEP_OK:
            return f"      ✓ ({ev.elapsed_s:.2f}s)"
        if ev.type == EventType.STEP_WARN:
            return f"      ⚠ {ev.message}"
        if ev.type == EventType.STEP_FAIL:
            return f"      ✗ {ev.message}"
        if ev.type == EventType.ROLLBACK_START:
            return f"\nRolling back {ev.total} step(s)..."
        if ev.type == EventType.ROLLBACK_STEP:
            return f"  rollback: {ev.step.title}"
        if ev.type == EventType.PLAN_OK:
            return f"\nDone in {ev.elapsed_s:.1f}s."
        if ev.type == EventType.PLAN_FAIL:
            return f"\nFAILED in {ev.elapsed_s:.1f}s."
        return ""
