"""alice-runtime adapter — register RecordorAI as the memory module
on the Bun gateway.

Skeleton only — Sprint 3 will read alice-runtime's memory-provider
contract (from the build plan under ~/.openclaw/plans/alice-runtime/)
and fill in plan_steps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Adapter

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class AliceRuntimeAdapter(Adapter):
    name = "alice-runtime"
    label = "alice-runtime"
    description = (
        "Register RecordorAI as the memory module on alice-runtime — the "
        "greenfield Bun gateway. (Coming in v0.2 once the alice-runtime "
        "memory contract stabilizes.)"
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "alice-runtime":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        # Sprint 3 will populate this with the alice-runtime
        # memory-module registration.
        return []

    def verify_description(self) -> str:
        return (
            "Sprint 3 will add a verify step that hits the alice-runtime "
            "/memory/health endpoint and confirms it's served by "
            "RecordorAI."
        )
