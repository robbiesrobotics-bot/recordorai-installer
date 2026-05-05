"""pi-mono adapter — RecordorAI as a TypeScript extension.

pi-mono (badlogic/pi-mono, the toolkit underlying OpenClaw) does
**not** have a formal "memory provider" abstraction the way Hermes
does. What it has is the **ExtensionAPI**:

  https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/extensions.md

Extensions are auto-discovered TypeScript files that register tools,
slash commands, keyboard shortcuts, and lifecycle event handlers. The
closest integration point for memory is the ``before_agent_start``
event — extensions can inject context into the system prompt or the
message history before each LLM turn.

So our integration shape is:

* Drop a TypeScript extension at
  ``~/.pi/agent/extensions/recordorai/index.ts`` that:
  - Registers a ``recordorai_search`` custom tool the agent can call.
  - Subscribes to ``before_agent_start`` and silently injects relevant
    memory context into the system prompt.
  - Spawns ``python -m recordorai.mcp_server`` as a stdio MCP server
    on first use, then routes tool calls through it (same pattern
    alice-runtime uses).

* Configure pi-mono to load the extension via ``settings.json``'s
  ``extensions`` array — pi-mono auto-discovers ``~/.pi/agent/extensions/*``
  but explicitly listing it makes the dependency visible to ``pi
  --list-extensions`` and similar CLI introspection.

The TypeScript shim is shipped as a templated payload. Sprint 5
swaps the inline template for a versioned npm publication so
``recordorai-pi-extension`` can be installed via ``pi extension add``
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Adapter

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class PiMonoAdapter(Adapter):
    name = "pi-mono"
    label = "pi-mono (Mario Zechner)"
    description = (
        "Drop a RecordorAI TypeScript extension under "
        "~/.pi/agent/extensions/recordorai/. Registers a "
        "`recordorai_search` tool and injects memory context via the "
        "`before_agent_start` event. Spawns RecordorAI's MCP server "
        "behind the scenes — no changes to pi-mono itself."
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "pi-mono":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        # pi-mono's extension root is per-user, not derivable from
        # `npm list -g` output reliably. Use the documented default.
        ext_root = "~/.pi/agent/extensions/recordorai"
        settings_path = "~/.pi/settings.json"

        return [
            Step(
                kind="fs",
                title="Create pi-mono extension directory",
                detail=(
                    f"Ensures {ext_root} exists. pi-mono "
                    "auto-discovers extensions from "
                    "~/.pi/agent/extensions/*/index.ts on next launch."
                ),
                metadata={"ext_root": ext_root},
            ),
            Step(
                kind="config",
                title="Drop extension index.ts",
                detail=(
                    f"Writes {ext_root}/index.ts — the extension "
                    "registers a `recordorai_search` tool + a "
                    "`before_agent_start` handler that calls "
                    "`recordorai_search` with the user's most recent "
                    "message and injects the top-K results into the "
                    "system prompt as a [Memory] block. The TS shim "
                    "spawns python -m recordorai.mcp_server lazily on "
                    "first use."
                ),
                metadata={"path": f"{ext_root}/index.ts"},
            ),
            Step(
                kind="config",
                title="Drop extension package.json",
                detail=(
                    f"Writes {ext_root}/package.json with the extension's "
                    "name, version, and the @mariozechner/pi-agent-core "
                    "peer dependency. Lets `pi --list-extensions` show "
                    "RecordorAI cleanly."
                ),
                metadata={"path": f"{ext_root}/package.json"},
            ),
            Step(
                kind="config",
                title="Register in pi-mono settings.json",
                detail=(
                    f"Edits {settings_path} to add "
                    "'~/.pi/agent/extensions/recordorai' to the "
                    "extensions array. Existing entries are preserved; "
                    "the previous JSON file is backed up to "
                    "settings.json.bak before the edit."
                ),
                metadata={"settings_path": settings_path},
            ),
            Step(
                kind="config",
                title="Set RECORDORAI_DB_PATH for pi-mono sessions",
                detail=(
                    f"Adds RECORDORAI_DB_PATH={choices.palace_root} to "
                    "the pi-mono environment so the spawned MCP server "
                    "uses the same palace as other integrations."
                ),
                metadata={"palace_root": choices.palace_root},
            ),
        ]

    def uninstall_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next((r for r in env.runtimes if r.name == "pi-mono"), None)
        if runtime is None or not runtime.detected:
            return []

        ext_root = "~/.pi/agent/extensions/recordorai"
        settings_path = "~/.pi/settings.json"

        return [
            Step(
                kind="config",
                title="Remove RecordorAI from pi-mono settings.json",
                detail=(
                    f"Edits {settings_path} to drop the recordorai "
                    "entry from the extensions array. Restored from the "
                    ".bak file if present."
                ),
                metadata={"settings_path": settings_path},
            ),
            Step(
                kind="fs",
                title="Remove RecordorAI extension directory",
                detail=f"Deletes {ext_root} and its files.",
                metadata={"ext_root": ext_root},
            ),
        ]

    def verify_description(self) -> str:
        return (
            "We'll run `pi --list-extensions` and confirm "
            "'recordorai' appears in the output. If pi is already "
            "running, you'll need to restart it for the extension to "
            "load."
        )
