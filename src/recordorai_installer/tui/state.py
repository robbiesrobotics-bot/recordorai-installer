"""Wizard state — flows between screens, settles into a Choices on submit.

Built incrementally as the user advances through screens. The final
screen calls :meth:`WizardState.to_choices` to freeze the state into
the immutable :class:`recordorai_installer.core.plan.Choices` instance
the planner consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.detect import Environment
from ..core.license import LicenseStatus
from ..core.plan import Choices


@dataclass
class WizardState:
    """Mutable wizard state. Each screen updates the fields it owns."""

    env: Environment

    # Screen 1 (Welcome) — user just sees detection summary; no input.

    # Screen 2 (Edition).
    edition: str = "community"
    license_key: str | None = None
    license_status: LicenseStatus | None = None

    # Screen 3 (Runtime).
    runtime: str = "standalone"

    # Screen 4 (Features).
    palace_root: str = ""
    enable_audio: bool = False
    enable_image: bool = False
    enable_video: bool = False
    enable_documents: bool = True
    enable_rerank_ane: bool = True

    # Pro-only — locked unless edition == "pro" and license is active.
    enable_multi_tenant: bool = False
    enable_sync: bool = False
    enable_smart_observer: bool = False

    # Screen 5 (Review + Install) — populated after build_plan.
    plan_summary: str = ""

    def __post_init__(self) -> None:
        if not self.palace_root:
            self.palace_root = str(Path.home() / ".recordorai")
        # ANE rerank only applies to Apple Silicon — auto-disable elsewhere.
        if not self.env.host.is_apple_silicon:
            self.enable_rerank_ane = False

    def to_choices(self) -> Choices:
        return Choices(
            runtime=self.runtime,
            palace_root=self.palace_root,
            edition=self.edition,
            license_key=self.license_key,
            enable_audio=self.enable_audio,
            enable_image=self.enable_image,
            enable_video=self.enable_video,
            enable_documents=self.enable_documents,
            enable_rerank_ane=self.enable_rerank_ane,
            enable_multi_tenant=self.enable_multi_tenant,
            enable_sync=self.enable_sync,
            enable_smart_observer=self.enable_smart_observer,
        )
