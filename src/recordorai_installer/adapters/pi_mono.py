"""pi-mono adapter — register RecordorAI as a memory provider on the
TypeScript pi-mono agent toolkit.

Skeleton only — Sprint 3 will read the pi-mono memory-provider
contract from ``@mariozechner/pi-agent-core`` and fill in the actual
plan_steps. For now, the adapter advertises eligibility (so the
wizard can show it as "coming soon") and returns an empty plan.
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
        "Register RecordorAI as a memory provider on pi-mono — the "
        "TypeScript agent toolkit underlying OpenClaw. (Coming in v0.2; "
        "select Standalone or OpenClaw for v0.1.)"
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "pi-mono":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        # Sprint 3 will populate this with:
        # 1. Drop a Node-side adapter under ~/.pi/memory-providers/recordorai/
        # 2. Register the provider in pi-mono's config
        # 3. Bridge the TS adapter to recordorai's Python API via stdio MCP
        return []

    def verify_description(self) -> str:
        return (
            "Sprint 3 will add a verify step that lists registered "
            "memory providers and confirms 'recordorai' is present."
        )
