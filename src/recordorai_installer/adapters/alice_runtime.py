"""alice-runtime adapter — point alice-runtime's McpMemoryClient at
RecordorAI.

alice-runtime (the Bun gateway) shipped Sprint 2.4 (2026-04-28) with
a built-in ``McpMemoryClient`` that already speaks recordorai's MCP
protocol. Reference:

  ~/.openclaw/plans/alice-runtime/08-recordorai-mcp-integration.md

So we don't add code to alice-runtime — we just configure it. The
adapter:

1. Edits alice-runtime's memory backend config (``~/.alice/config.toml``
   or the equivalent project-local file) to set
   ``[memory] backend = "recordorai-mcp"``.
2. Sets the env vars the McpStdioSupervisor expects:
   - ``RECORDORAI_DB_PATH``
   - ``RECORDORAI_RERANK_BACKEND=coreml`` on Apple Silicon, ``pytorch``
     elsewhere.
3. Verifies via ``alice memory health`` that the supervisor can spawn
   the MCP subprocess and complete the JSON-RPC ``initialize``
   handshake.

If alice-runtime isn't yet shipped on the user's machine but we
detected its install dir (e.g. ``~/.alice/`` exists from a checkout),
we still write the config so a future ``alice install`` picks it up.
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
        "Configure alice-runtime to use RecordorAI as its memory "
        "backend via the built-in McpMemoryClient (Sprint 2.4+). "
        "No code change to alice-runtime — just sets the backend "
        "selector + env vars + verifies the JSON-RPC handshake."
    )

    def is_eligible(self, env: Environment) -> bool:
        for r in env.runtimes:
            if r.name == "alice-runtime":
                return r.detected
        return False

    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next(r for r in env.runtimes if r.name == "alice-runtime")
        alice_root = runtime.install_path or "~/.alice"
        config_path = f"{alice_root}/config.toml"
        rerank_backend = "coreml" if env.host.is_apple_silicon else "pytorch"

        return [
            Step(
                kind="config",
                title="Set alice-runtime memory.backend = recordorai-mcp",
                detail=(
                    f"Edits {config_path} so [memory] backend = "
                    "'recordorai-mcp'. The previous backend is "
                    "preserved at memory.backend_backup so uninstall "
                    "can revert."
                ),
                metadata={
                    "config_path": config_path,
                    "alice_root": alice_root,
                },
            ),
            Step(
                kind="config",
                title="Set memory.python_bin to /usr/bin/python3",
                detail=(
                    "alice-runtime's McpStdioSupervisor needs a "
                    "Python interpreter that has coremltools installed. "
                    "On macOS that's the Xcode-bundled "
                    "/usr/bin/python3; on other platforms it's "
                    "whatever the user's `python3` resolves to."
                ),
                metadata={
                    "config_path": config_path,
                    "alice_root": alice_root,
                },
            ),
            Step(
                kind="config",
                title=f"Set memory.rerank_backend = {rerank_backend!r}",
                detail=(
                    "Picks the rerank engine based on the host. CoreML "
                    "on Apple Silicon (M-series Neural Engine, ~190 ms "
                    "p50) and PyTorch elsewhere (CPU/GPU fallback)."
                ),
                metadata={
                    "config_path": config_path,
                    "rerank_backend": rerank_backend,
                    "alice_root": alice_root,
                },
            ),
            Step(
                kind="config",
                title="Set RECORDORAI_DB_PATH for alice-runtime sessions",
                detail=(
                    f"Adds RECORDORAI_DB_PATH={choices.palace_root} to "
                    f"{alice_root}/.env so the spawned MCP supervisor "
                    "uses the same palace as the other integrations."
                ),
                metadata={
                    "palace_root": choices.palace_root,
                    "alice_root": alice_root,
                },
            ),
        ]

    def uninstall_steps(self, env: Environment, choices: Choices) -> list[Step]:
        from ..core.plan import Step

        runtime = next((r for r in env.runtimes if r.name == "alice-runtime"), None)
        if runtime is None or not runtime.detected:
            return []
        alice_root = runtime.install_path or "~/.alice"

        return [
            Step(
                kind="config",
                title="Restore alice-runtime memory.backend",
                detail=(
                    f"Reverts {alice_root}/config.toml's "
                    "[memory].backend to whatever was set before "
                    "(preserved as memory.backend_backup)."
                ),
                metadata={"alice_root": alice_root},
            ),
        ]

    def verify_description(self) -> str:
        return (
            "We'll run `alice memory health` and confirm the "
            "McpMemoryClient successfully spawns the recordorai MCP "
            "subprocess and completes the JSON-RPC initialize "
            "handshake."
        )
