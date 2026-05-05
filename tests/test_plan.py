"""Tests for recordorai_installer.core.plan."""

from __future__ import annotations

from recordorai_installer.core.plan import Choices, build_plan


class TestBuildPlan:
    def test_minimal_plan_has_preflight_deps_fs_register_verify(self, fake_env_macos_arm64):
        choices = Choices(runtime="standalone", palace_root="/tmp/test-palace")
        plan = build_plan(fake_env_macos_arm64, choices)

        kinds = plan.kinds()
        assert "verify" in kinds
        assert "deps" in kinds
        assert "fs" in kinds
        assert plan.summary  # non-empty

    def test_plan_includes_document_extras_when_documents_enabled(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            enable_documents=True,
        )
        plan = build_plan(fake_env_macos_arm64, choices)

        deps = plan.by_kind("deps")
        assert len(deps) == 1
        assert "document-all" in deps[0].metadata["extras"]

    def test_plan_omits_audio_extras_when_audio_disabled(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            enable_audio=False,
            enable_image=False,
            enable_video=False,
        )
        plan = build_plan(fake_env_macos_arm64, choices)

        deps_step = plan.by_kind("deps")[0]
        extras = deps_step.metadata["extras"]
        assert "multimodal-audio" not in extras
        assert "multimodal-image" not in extras
        assert "multimodal-video" not in extras

    def test_plan_includes_ane_only_on_apple_silicon(
        self, fake_env_macos_arm64, fake_env_linux_x86
    ):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            enable_rerank_ane=True,
        )
        mac_plan = build_plan(fake_env_macos_arm64, choices)
        lx_plan = build_plan(fake_env_linux_x86, choices)

        assert "multimodal-rerank" in mac_plan.by_kind("deps")[0].metadata["extras"]
        assert "multimodal-rerank" not in lx_plan.by_kind("deps")[0].metadata["extras"]

    def test_video_adds_ffmpeg_preflight_check(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            enable_video=True,
        )
        plan = build_plan(fake_env_macos_arm64, choices)
        verify_titles = [s.title for s in plan.by_kind("verify")]
        assert any("ffmpeg" in t for t in verify_titles)

    def test_pro_edition_adds_license_step(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            edition="pro",
            license_key="RAI-PRO-VALID-XXXX",
        )
        plan = build_plan(fake_env_macos_arm64, choices)
        license_steps = plan.by_kind("license")
        assert len(license_steps) == 1
        assert license_steps[0].metadata["license_key"] == "RAI-PRO-VALID-XXXX"

    def test_community_edition_skips_license_step(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="standalone",
            palace_root="/tmp/test-palace",
            edition="community",
        )
        plan = build_plan(fake_env_macos_arm64, choices)
        assert plan.by_kind("license") == []

    def test_openclaw_runtime_appends_adapter_steps(self, fake_env_with_openclaw):
        choices = Choices(
            runtime="openclaw",
            palace_root="/tmp/test-palace",
        )
        plan = build_plan(fake_env_with_openclaw, choices)

        # OpenClaw adapter contributes register + config + fs steps.
        titles = [s.title for s in plan.steps]
        assert any("qmd-recordorai-shim" in t for t in titles)
        assert any("openclaw.json" in t for t in titles)

    def test_summary_mentions_runtime_and_features(self, fake_env_macos_arm64):
        choices = Choices(
            runtime="openclaw",
            palace_root="/home/x/.recordorai",
            enable_documents=True,
        )
        plan = build_plan(fake_env_macos_arm64, choices)
        assert "openclaw" in plan.summary
        assert ".recordorai" in plan.summary
