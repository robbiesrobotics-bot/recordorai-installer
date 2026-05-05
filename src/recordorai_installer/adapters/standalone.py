"""Standalone adapter — install RecordorAI with no host runtime.

This is the "default" path: drop the ``recordorai`` CLI on PATH,
expose the Python API, and ship the MCP server as a separate command
the user can wire into any compliant client.

The adapter is always eligible (every machine can run standalone).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Adapter

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class StandaloneAdapter(Adapter):
    name = "standalone"
    label = "Standalone"
    description = (
        "Install RecordorAI on its own. Provides the `recordorai` CLI, "
        "the Python API, and a standalone MCP server you can wire into "
        "any compliant client. Use this if you don't have OpenClaw, "
        "pi-mono, alice-runtime, or Hermes Agent installed."
    )

    def is_eligible(self, env: Environment) -> bool:
        return True

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        steps: list[Step] = [
            Step(
                kind="config",
                title="Write standalone config",
                detail=(
                    "Creates ~/.recordorai/config.toml with default settings. "
                    "Existing configs are preserved (this is a no-op upgrade)."
                ),
                metadata={
                    "config_path": f"{choices.palace_root}/config.toml",
                    "runtime": "standalone",
                },
            ),
            Step(
                kind="register",
                title="Verify `recordorai` CLI on PATH",
                detail=(
                    "After `pip install recordorai`, the entry-point script "
                    "lands in your Python's bin directory. We confirm it's "
                    "reachable so you can run `recordorai search ...` from any "
                    "terminal."
                ),
                metadata={"runtime": "standalone"},
            ),
        ]
        return steps

    def verify_description(self) -> str:
        return (
            "We'll run `recordorai --version` to confirm the CLI works "
            "and `python -c 'import recordorai'` to confirm the API is "
            "importable."
        )
