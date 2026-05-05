"""OpenClaw adapter — wire RecordorAI into OpenClaw as the memory provider.

Integration shape (matches the existing production deployment under
``~/.openclaw/``):

1. Drop the ``qmd-recordorai-shim`` script in ``~/.openclaw/bin/``.
   The shim is a stdio MCP server speaking qmd's protocol; it routes
   ``memory_search`` / ``memory_get`` through ``recordorai.searcher``.

2. Edit ``~/.openclaw/openclaw.json`` so ``memory.qmd.command`` points
   at the shim. Existing memory backend configs are preserved as
   commented-out backups so the user can revert.

3. Register hooks (``recordorai_save_hook.sh``, the precompact hook)
   under ``~/.openclaw/hooks/`` so OpenClaw triggers RecordorAI
   ingest at the right lifecycle moments.

The adapter is eligible iff the wizard detected an OpenClaw install.
On uninstall, every change above is reversed (shim deleted, config
restored, hooks unregistered).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Adapter

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class OpenClawAdapter(Adapter):
    name = "openclaw"
    label = "OpenClaw"
    description = (
        "Replace OpenClaw's default memory backend with RecordorAI. "
        "Adds the qmd-recordorai-shim under ~/.openclaw/bin/ and points "
        "OpenClaw's memory.qmd.command at it. Hooks fire on conversation "
        "stop / pre-compact so memory ingest happens automatically."
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "openclaw":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        # The OpenClaw runtime info object is guaranteed present when
        # this adapter is eligible.
        runtime = next(r for r in env.runtimes if r.name == "openclaw")
        openclaw_root = runtime.install_path or "~/.openclaw"
        bin_dir = f"{openclaw_root}/bin"
        config_path = f"{openclaw_root}/openclaw.json"
        hooks_dir = f"{openclaw_root}/hooks"

        return [
            Step(
                kind="fs",
                title="Create OpenClaw bin + hooks directories",
                detail=(
                    f"Ensures {bin_dir} and {hooks_dir} exist. "
                    "Both are created with user-only permissions."
                ),
                metadata={
                    "bin_dir": bin_dir,
                    "hooks_dir": hooks_dir,
                    "openclaw_root": openclaw_root,
                },
            ),
            Step(
                kind="config",
                title="Drop qmd-recordorai-shim",
                detail=(
                    f"Copies the shim to {bin_dir}/qmd-recordorai-shim and "
                    "marks it executable. The shim is a small stdio MCP "
                    "server that speaks qmd's protocol but routes memory "
                    "queries through RecordorAI's rerank pipeline."
                ),
                metadata={
                    "shim_path": f"{bin_dir}/qmd-recordorai-shim",
                    "openclaw_root": openclaw_root,
                },
            ),
            Step(
                kind="config",
                title="Patch openclaw.json memory.qmd.command",
                detail=(
                    f"Edits {config_path} to set "
                    "memory.qmd.command -> the shim path. The previous "
                    "value is preserved under memory.qmd.command_backup so "
                    "uninstall can revert cleanly."
                ),
                metadata={
                    "config_path": config_path,
                    "key": "memory.qmd.command",
                    "openclaw_root": openclaw_root,
                },
            ),
            Step(
                kind="register",
                title="Install OpenClaw hooks",
                detail=(
                    f"Drops recordorai_save_hook.sh and "
                    "recordorai_precompact_hook.sh into "
                    f"{hooks_dir}. Each hook calls into the recordorai "
                    "package via the OpenClaw runtime Python."
                ),
                metadata={
                    "hooks_dir": hooks_dir,
                    "openclaw_root": openclaw_root,
                },
            ),
            Step(
                kind="config",
                title="Set RECORDORAI_DB_PATH for OpenClaw sessions",
                detail=(
                    f"Adds RECORDORAI_DB_PATH={choices.palace_root} to "
                    f"OpenClaw's environment so the shim and hooks share "
                    "a single palace."
                ),
                metadata={
                    "palace_root": choices.palace_root,
                    "openclaw_root": openclaw_root,
                },
            ),
        ]

    def uninstall_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next((r for r in env.runtimes if r.name == "openclaw"), None)
        if runtime is None or not runtime.detected:
            return []
        openclaw_root = runtime.install_path or "~/.openclaw"

        return [
            Step(
                kind="config",
                title="Restore openclaw.json memory.qmd.command",
                detail=(
                    "Reverts memory.qmd.command to the value stored under "
                    "memory.qmd.command_backup."
                ),
                metadata={"openclaw_root": openclaw_root},
            ),
            Step(
                kind="fs",
                title="Remove qmd-recordorai-shim",
                detail=f"Deletes {openclaw_root}/bin/qmd-recordorai-shim.",
                metadata={"openclaw_root": openclaw_root},
            ),
            Step(
                kind="fs",
                title="Remove RecordorAI hooks",
                detail=(
                    f"Deletes recordorai_save_hook.sh and "
                    f"recordorai_precompact_hook.sh from {openclaw_root}/hooks/."
                ),
                metadata={"openclaw_root": openclaw_root},
            ),
        ]

    def verify_description(self) -> str:
        return (
            "We'll spawn the shim with `--probe` and confirm it returns "
            "the expected qmd tool list (query / get / multi_get / "
            "status). If OpenClaw is running, we'll also confirm it can "
            "load the new memory.qmd.command without errors."
        )
