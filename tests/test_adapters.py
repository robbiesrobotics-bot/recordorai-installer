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


class TestEligibilityForUndetectedRuntimes:
    """When the runtime isn't detected, the adapter must NOT advertise
    itself as eligible — even if a user-typed runtime name happens to
    match. The wizard hides ineligible adapters in the picker.
    """

    @pytest.mark.parametrize("name", ["pi-mono", "alice-runtime", "hermes"])
    def test_adapter_ineligible_when_runtime_absent(self, fake_env_macos_arm64, name):
        ad = get_adapter(name)
        assert ad.is_eligible(fake_env_macos_arm64) is False
        # plan_steps is allowed to crash on an ineligible env because
        # the wizard never reaches an ineligible adapter. We only
        # assert the adapter loads + answers eligibility correctly.


class TestHermesAdapter:
    def test_eligible_only_when_hermes_detected(self, fake_env_macos_arm64, fake_env_with_hermes):
        ad = get_adapter("hermes")
        assert ad.is_eligible(fake_env_macos_arm64) is False
        assert ad.is_eligible(fake_env_with_hermes) is True

    def test_plan_drops_three_plugin_files_under_plugin_dir(self, fake_env_with_hermes):
        ad = get_adapter("hermes")
        choices = Choices(runtime="hermes", palace_root="/tmp/p")
        steps = ad.plan_steps(fake_env_with_hermes, choices)
        titles = [s.title for s in steps]
        # Required plugin files: __init__.py + plugin.yaml + README.md.
        assert any("__init__.py" in t for t in titles)
        assert any("plugin.yaml" in t for t in titles)
        assert any("README.md" in t for t in titles)

    def test_plan_includes_palace_env_var_step(self, fake_env_with_hermes):
        ad = get_adapter("hermes")
        choices = Choices(runtime="hermes", palace_root="/var/recordorai")
        steps = ad.plan_steps(fake_env_with_hermes, choices)
        env_steps = [s for s in steps if "RECORDORAI_DB_PATH" in s.title]
        assert len(env_steps) == 1
        assert env_steps[0].metadata["palace_root"] == "/var/recordorai"

    def test_plan_includes_user_action_step_for_hermes_setup(self, fake_env_with_hermes):
        """Hermes activation requires the interactive `hermes memory
        setup` command — the installer must call this out explicitly
        rather than silently fail to activate.
        """
        ad = get_adapter("hermes")
        choices = Choices(runtime="hermes", palace_root="/tmp/x")
        steps = ad.plan_steps(fake_env_with_hermes, choices)
        titles = " | ".join(s.title for s in steps)
        assert "hermes memory setup" in titles

    def test_uninstall_removes_plugin_dir_and_restores_active_provider(self, fake_env_with_hermes):
        ad = get_adapter("hermes")
        choices = Choices(runtime="hermes", palace_root="/tmp/x")
        steps = ad.uninstall_steps(fake_env_with_hermes, choices)
        titles = [s.title for s in steps]
        assert any("active memory provider" in t for t in titles)
        assert any("plugin directory" in t for t in titles)


class TestPiMonoAdapter:
    def test_eligible_only_when_pi_mono_detected(self, fake_env_macos_arm64, fake_env_with_pi_mono):
        ad = get_adapter("pi-mono")
        assert ad.is_eligible(fake_env_macos_arm64) is False
        assert ad.is_eligible(fake_env_with_pi_mono) is True

    def test_plan_drops_typescript_extension_files(self, fake_env_with_pi_mono):
        ad = get_adapter("pi-mono")
        choices = Choices(runtime="pi-mono", palace_root="/tmp/p")
        steps = ad.plan_steps(fake_env_with_pi_mono, choices)
        titles = [s.title for s in steps]
        # The extension is shipped as index.ts + package.json under
        # ~/.pi/agent/extensions/recordorai/.
        assert any("index.ts" in t for t in titles)
        assert any("package.json" in t for t in titles)

    def test_plan_registers_in_settings_json(self, fake_env_with_pi_mono):
        ad = get_adapter("pi-mono")
        choices = Choices(runtime="pi-mono", palace_root="/tmp/p")
        steps = ad.plan_steps(fake_env_with_pi_mono, choices)
        register_steps = [s for s in steps if "settings.json" in s.title]
        assert len(register_steps) == 1
        assert register_steps[0].metadata["settings_path"] == "~/.pi/settings.json"

    def test_uninstall_unregisters_and_removes_dir(self, fake_env_with_pi_mono):
        ad = get_adapter("pi-mono")
        choices = Choices(runtime="pi-mono", palace_root="/tmp/p")
        steps = ad.uninstall_steps(fake_env_with_pi_mono, choices)
        titles = [s.title for s in steps]
        assert any("settings.json" in t for t in titles)
        assert any("extension directory" in t for t in titles)


class TestAliceRuntimeAdapter:
    def test_eligible_only_when_alice_detected(
        self, fake_env_macos_arm64, fake_env_with_alice_runtime
    ):
        ad = get_adapter("alice-runtime")
        assert ad.is_eligible(fake_env_macos_arm64) is False
        assert ad.is_eligible(fake_env_with_alice_runtime) is True

    def test_plan_sets_recordorai_mcp_backend(self, fake_env_with_alice_runtime):
        ad = get_adapter("alice-runtime")
        choices = Choices(runtime="alice-runtime", palace_root="/tmp/p")
        steps = ad.plan_steps(fake_env_with_alice_runtime, choices)
        titles = " | ".join(s.title for s in steps)
        assert "recordorai-mcp" in titles

    def test_plan_picks_coreml_rerank_on_apple_silicon(self, fake_env_with_alice_runtime):
        ad = get_adapter("alice-runtime")
        choices = Choices(runtime="alice-runtime", palace_root="/tmp/p")
        steps = ad.plan_steps(fake_env_with_alice_runtime, choices)
        rerank_steps = [s for s in steps if "rerank_backend" in s.metadata]
        assert len(rerank_steps) == 1
        assert rerank_steps[0].metadata["rerank_backend"] == "coreml"

    def test_plan_picks_pytorch_rerank_off_apple_silicon(self, fake_env_with_alice_runtime):
        # Re-shape the env to non-Apple-Silicon and re-run.
        from recordorai_installer.core.detect import GPUInfo, HostInfo

        env = fake_env_with_alice_runtime
        env_obj = type(env)(
            host=HostInfo(os="linux", arch="x86_64", os_version="6.5", is_apple_silicon=False),
            python=env.python,
            gpu=GPUInfo(
                has_apple_neural_engine=False,
                has_cuda=False,
                has_rocm=False,
            ),
            runtimes=env.runtimes,
            existing_recordorai=env.existing_recordorai,
            palace_root=env.palace_root,
        )
        ad = get_adapter("alice-runtime")
        choices = Choices(runtime="alice-runtime", palace_root="/tmp/p")
        steps = ad.plan_steps(env_obj, choices)
        rerank_steps = [s for s in steps if "rerank_backend" in s.metadata]
        assert rerank_steps[0].metadata["rerank_backend"] == "pytorch"

    def test_uninstall_restores_previous_backend(self, fake_env_with_alice_runtime):
        ad = get_adapter("alice-runtime")
        choices = Choices(runtime="alice-runtime", palace_root="/tmp/p")
        steps = ad.uninstall_steps(fake_env_with_alice_runtime, choices)
        titles = [s.title for s in steps]
        assert any("Restore" in t and "backend" in t for t in titles)
