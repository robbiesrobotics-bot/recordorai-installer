"""Hermes Agent adapter — RecordorAI as a memory-provider plugin.

Hermes Agent (NousResearch) ships with a documented plugin
architecture for memory providers. Reference:

  https://hermes-agent.nousresearch.com/docs/developer-guide/memory-provider-plugin
  https://github.com/NousResearch/hermes-agent/blob/main/agent/memory_provider.py

A provider plugin is a directory under ``<hermes_home>/plugins/memory/<name>/``
containing:

* ``__init__.py``  — implementation of the abstract ``MemoryProvider``
                     class plus a ``register(ctx)`` entry point that
                     calls ``ctx.register_memory_provider(<instance>)``.
* ``plugin.yaml``  — metadata: ``name``, ``version``, ``description``,
                     ``hooks`` list.
* ``README.md``    — setup instructions.

Activation flow (one-time, after the plugin is on disk):

    $ hermes memory setup
    → wizard prompts for fields declared by ``get_config_schema()``
    → marks ``recordorai`` as the active provider in Hermes config

The installer:

1. Resolves ``hermes_home`` (defaults to ``~/.hermes``; can be
   overridden by ``HERMES_HOME`` env var).
2. Drops the provider plugin under
   ``<hermes_home>/plugins/memory/recordorai/``.
3. Sets ``RECORDORAI_DB_PATH`` so the plugin and any other RecordorAI
   integration share a single palace.
4. Tells the user to run ``hermes memory setup`` to finish activation
   (we don't run that command for them — it's an interactive prompt
   loop and the user needs to see it).

The provider implementation is shipped as a templated payload —
Sprint 5 will replace the ``hermes memory setup`` instructions with
direct config-file edits once we've verified the schema is stable.
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
        "Register RecordorAI as a memory-provider plugin on Hermes "
        "Agent. Drops a Python plugin under "
        "~/.hermes/plugins/memory/recordorai/ that wraps "
        "recordorai.searcher behind the standard MemoryProvider ABC. "
        "After install, run `hermes memory setup` to finish activation."
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "hermes":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next(r for r in env.runtimes if r.name == "hermes")
        hermes_home = self._hermes_home(runtime)
        plugin_dir = f"{hermes_home}/plugins/memory/recordorai"

        return [
            Step(
                kind="fs",
                title="Create Hermes plugin directory",
                detail=(
                    f"Ensures {plugin_dir} exists with user-only "
                    "permissions. Hermes auto-discovers plugins from "
                    "<hermes_home>/plugins/memory/* on next launch."
                ),
                metadata={"plugin_dir": plugin_dir, "hermes_home": hermes_home},
            ),
            Step(
                kind="config",
                title="Drop plugin __init__.py",
                detail=(
                    "Writes the MemoryProvider subclass + register(ctx) "
                    "entry point. The provider implements the four "
                    "required abstract methods (name, is_available, "
                    "initialize, get_tool_schemas) and overrides "
                    "system_prompt_block + prefetch + sync_turn for "
                    "RecordorAI's hybrid retrieval."
                ),
                metadata={
                    "path": f"{plugin_dir}/__init__.py",
                    "hermes_home": hermes_home,
                },
            ),
            Step(
                kind="config",
                title="Drop plugin.yaml",
                detail=(
                    f"Writes {plugin_dir}/plugin.yaml with "
                    "name=recordorai, version, description, and the hook "
                    "list (sync_turn, on_session_end). Hermes reads this "
                    "to drive the setup wizard and the lifecycle dispatch."
                ),
                metadata={
                    "path": f"{plugin_dir}/plugin.yaml",
                    "hermes_home": hermes_home,
                },
            ),
            Step(
                kind="config",
                title="Drop plugin README.md",
                detail=(
                    "Setup instructions visible from `hermes plugins "
                    "info recordorai`. Mirrors what Hermes' built-in "
                    "providers ship."
                ),
                metadata={
                    "path": f"{plugin_dir}/README.md",
                    "hermes_home": hermes_home,
                },
            ),
            Step(
                kind="config",
                title="Set RECORDORAI_DB_PATH for Hermes sessions",
                detail=(
                    f"Adds RECORDORAI_DB_PATH={choices.palace_root} to "
                    f"{hermes_home}/.env so the plugin and any other "
                    "RecordorAI integration on this machine share a "
                    "single palace."
                ),
                metadata={
                    "palace_root": choices.palace_root,
                    "hermes_home": hermes_home,
                },
            ),
            Step(
                kind="register",
                title="Tell the user to run `hermes memory setup`",
                detail=(
                    "Final activation is interactive — Hermes' setup "
                    "wizard prompts for any provider config fields and "
                    "writes them to the right places. The wizard will "
                    "now see 'recordorai' alongside the built-in "
                    "providers."
                ),
                metadata={"hermes_home": hermes_home},
            ),
        ]

    def uninstall_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next((r for r in env.runtimes if r.name == "hermes"), None)
        if runtime is None or not runtime.detected:
            return []
        hermes_home = self._hermes_home(runtime)
        plugin_dir = f"{hermes_home}/plugins/memory/recordorai"

        return [
            Step(
                kind="config",
                title="Restore Hermes' previous active memory provider",
                detail=(
                    f"Edits {hermes_home}/config to revert "
                    "memory.active_provider to whatever was set before "
                    "RecordorAI was installed (preserved as "
                    "memory.active_provider_backup)."
                ),
                metadata={"hermes_home": hermes_home},
            ),
            Step(
                kind="fs",
                title="Remove RecordorAI plugin directory",
                detail=f"Deletes {plugin_dir} and its three files.",
                metadata={"plugin_dir": plugin_dir, "hermes_home": hermes_home},
            ),
        ]

    def verify_description(self) -> str:
        return (
            "We'll run `hermes plugins list` and confirm "
            "'recordorai' appears with status=available. If Hermes is "
            "already running, you'll need to restart it for the plugin "
            "to load."
        )

    # ── Internals ────────────────────────────────────────────────────────

    @staticmethod
    def _hermes_home(runtime) -> str:
        """Resolve <hermes_home>. Hermes' own convention is the
        ``HERMES_HOME`` env var, falling back to ``~/.hermes``. Our
        detector picks up the latter via the directory probe; if the
        user has a custom HERMES_HOME we'll catch it via env in a
        Sprint 4 enhancement.
        """
        # When detect.py finds Hermes via `hermes` on PATH it sets
        # install_path to the bin directory, not hermes_home. Fall back
        # to the canonical default in that case.
        ip = runtime.install_path or ""
        if ip and ip.endswith("/.hermes"):
            return ip
        return "~/.hermes"
