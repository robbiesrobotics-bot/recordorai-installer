"""Tests for recordorai_installer.adapters."""

from __future__ import annotations

import pytest

from recordorai_installer.adapters import get_adapter, supported_runtimes
from recordorai_installer.adapters.base import Adapter
from recordorai_installer.core.plan import Choices


class TestRegistry:
    def test_supported_runtimes_lists_all_five(self):
        assert sorted(supported_runtimes()) == sorted(
            ["standalone", "openclaw", "pi-mono", "alice-runtime", "hermes"]
        )

    def test_get_adapter_returns_instance_per_name(self):
        for name in supported_runtimes():
            ad = get_adapter(name)
            assert isinstance(ad, Adapter)
            assert ad.name == name

    def test_get_adapter_raises_for_unknown(self):
        with pytest.raises(KeyError):
            get_adapter("not-a-real-runtime")


class TestStandaloneAdapter:
    def test_always_eligible(self, fake_env_macos_arm64, fake_env_linux_x86):
        ad = get_adapter("standalone")
        assert ad.is_eligible(fake_env_macos_arm64) is True
        assert ad.is_eligible(fake_env_linux_x86) is True

    def test_plan_steps_include_config_and_register(self, fake_env_macos_arm64):
        ad = get_adapter("standalone")
        choices = Choices(runtime="standalone", palace_root="/tmp/x")
        steps = ad.plan_steps(fake_env_macos_arm64, choices)
        kinds = {s.kind for s in steps}
        assert "config" in kinds
        assert "register" in kinds

    def test_verify_description_is_non_empty(self):
        assert len(get_adapter("standalone").verify_description()) > 0


class TestOpenClawAdapter:
    def test_eligible_only_when_openclaw_detected(
        self, fake_env_macos_arm64, fake_env_with_openclaw
    ):
        ad = get_adapter("openclaw")
        assert ad.is_eligible(fake_env_macos_arm64) is False
        assert ad.is_eligible(fake_env_with_openclaw) is True

    def test_plan_steps_include_shim_and_config_patch(self, fake_env_with_openclaw):
        ad = get_adapter("openclaw")
        choices = Choices(runtime="openclaw", palace_root="/tmp/x")
        steps = ad.plan_steps(fake_env_with_openclaw, choices)

        titles = [s.title for s in steps]
        assert any("qmd-recordorai-shim" in t for t in titles)
        assert any("openclaw.json" in t for t in titles)
        assert any("hooks" in t.lower() for t in titles)

    def test_uninstall_steps_reverse_install(self, fake_env_with_openclaw):
        ad = get_adapter("openclaw")
        choices = Choices(runtime="openclaw", palace_root="/tmp/x")
        steps = ad.uninstall_steps(fake_env_with_openclaw, choices)
        assert len(steps) >= 1
        titles = [s.title for s in steps]
        assert any("Restore" in t or "Remove" in t for t in titles)

    def test_uninstall_steps_empty_when_openclaw_absent(self, fake_env_macos_arm64):
        ad = get_adapter("openclaw")
        choices = Choices(runtime="openclaw", palace_root="/tmp/x")
        assert ad.uninstall_steps(fake_env_macos_arm64, choices) == []


class TestSkeletonAdapters:
    """pi-mono / alice-runtime / hermes are skeletons in Sprint 1.

    Each must implement the ABC so the registry can load them, but
    plan_steps may return [] until Sprint 3.
    """

    @pytest.mark.parametrize("name", ["pi-mono", "alice-runtime", "hermes"])
    def test_skeleton_adapter_is_loadable(self, fake_env_macos_arm64, name):
        ad = get_adapter(name)
        assert ad.name == name
        assert ad.label  # human-readable label exists
        assert ad.description  # non-empty description
        # Skeleton adapters return [] for plan_steps when the runtime
        # isn't detected (or even when it is — Sprint 3 fills in).
        choices = Choices(runtime=name, palace_root="/tmp/x")
        assert ad.plan_steps(fake_env_macos_arm64, choices) == []
