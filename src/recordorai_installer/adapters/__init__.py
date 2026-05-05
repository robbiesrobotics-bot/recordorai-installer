"""Per-runtime adapters.

Each adapter knows how to:

1. Tell the wizard whether it's eligible (``is_eligible``).
2. Add runtime-specific :class:`recordorai_installer.core.plan.Step`
   instances to the plan (``plan_steps``).
3. Reverse the integration cleanly when the user uninstalls
   (``uninstall_steps``).

Adapter modules import lazily inside :func:`get_adapter` so the
package doesn't pay the cost of importing all five at startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Adapter


# Registered adapter identifiers — extend the dict here when adding a
# new runtime in Sprint 3.
_ADAPTERS = {
    "standalone": "recordorai_installer.adapters.standalone:StandaloneAdapter",
    "openclaw": "recordorai_installer.adapters.openclaw:OpenClawAdapter",
    "pi-mono": "recordorai_installer.adapters.pi_mono:PiMonoAdapter",
    "alice-runtime": "recordorai_installer.adapters.alice_runtime:AliceRuntimeAdapter",
    "hermes": "recordorai_installer.adapters.hermes:HermesAdapter",
}


def get_adapter(name: str) -> Adapter:
    """Return the adapter instance for the given runtime name."""
    if name not in _ADAPTERS:
        raise KeyError(f"Unknown runtime {name!r}. Known: {sorted(_ADAPTERS)}")
    module_path, cls_name = _ADAPTERS[name].split(":")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, cls_name)()


def supported_runtimes() -> list[str]:
    """Names of every adapter the wizard knows about."""
    return list(_ADAPTERS.keys())
