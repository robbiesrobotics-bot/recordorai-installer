"""Hermes Agent adapter — register RecordorAI as a memory provider
plugin on the NousResearch Hermes Agent runtime.

Hermes Agent (github.com/NousResearch/hermes-agent) ships with a
pluggable memory provider architecture; existing third-party
providers include Honcho and Supermemory. RecordorAI plugs into the
same lifecycle hooks via a small Python adapter shipped under
``~/.hermes/memory-providers/recordorai/``.

Skeleton only — Sprint 3 will:

1. Read the memory-provider contract from
   https://hermes-agent.nousresearch.com/docs/.
2. Implement the provider class (subclasses the Hermes
   ``MemoryProvider`` ABC).
3. Drop the provider entry-point so Hermes loads it on next launch.
4. Patch ``~/.hermes/config.toml`` to set the active memory provider
   to ``recordorai``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Adapter

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class HermesAdapter(Adapter):
    name = "hermes"
    label = "Hermes Agent (NousResearch)"
    description = (
        "Register RecordorAI as a memory provider plugin on Hermes "
        "Agent. Replaces the default FTS5+LLM memory layer with "
        "RecordorAI's rerank pipeline. (Coming in v0.2.)"
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "hermes":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        # Sprint 3 will populate this with the Hermes memory-provider
        # plugin install.
        return []

    def verify_description(self) -> str:
        return (
            "Sprint 3 will add a verify step that lists Hermes' active "
            "memory provider and confirms it's RecordorAI."
        )
