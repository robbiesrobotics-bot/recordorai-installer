"""Adapter abstract base class.

Every runtime adapter implements three concerns:

1. **Eligibility** — ``is_eligible(env)`` returns False for the wizard
   to skip this runtime in the picker. Standalone is always eligible;
   the others gate on whether the host runtime is detected.

2. **Install plan** — ``plan_steps(env, choices)`` returns the
   runtime-specific :class:`Step` instances appended to the global
   plan during :func:`recordorai_installer.core.plan.build_plan`.

3. **Verification** — ``verify_description()`` is the one-line text
   shown on the final verify step ("we'll check that OpenClaw can
   load the shim").

Adapters are stateless — instances are cheap to create and don't hold
references to the environment they operate on.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.detect import Environment
    from ..core.plan import Choices, Step


class Adapter(ABC):
    """Common contract for every runtime integration."""

    #: One of: standalone | openclaw | pi-mono | alice-runtime | hermes
    name: str = ""

    #: Human-readable label shown in the wizard's runtime picker.
    label: str = ""

    #: Multi-line description shown when the user hovers / focuses
    #: this runtime in the picker.
    description: str = ""

    @abstractmethod
    def is_eligible(self, env: Environment) -> bool:
        """Return True iff this adapter can integrate with the
        environment as detected. The wizard hides ineligible adapters
        (e.g. OpenClaw on a machine without OpenClaw installed).
        """

    @abstractmethod
    def plan_steps(self, env: Environment, choices: Choices) -> list[Step]:
        """Return the ordered list of runtime-specific steps to append
        to the global install plan.
        """

    def uninstall_steps(self, env: Environment, choices: Choices) -> list[Step]:
        """Return the ordered list of steps to reverse this adapter's
        install. Default: empty (subclasses override when they have
        side effects to undo).
        """
        return []

    @abstractmethod
    def verify_description(self) -> str:
        """One-line description of the verification check, shown in the
        final verify step's detail field.
        """
