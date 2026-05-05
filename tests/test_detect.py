"""Tests for recordorai_installer.core.detect.

Each detector is exercised through real syscalls (no mocking) since
detect.py is intentionally light on external state. Tests run on
whatever OS the CI matrix is sitting on; expectations are
machine-agnostic.
"""

from __future__ import annotations

from pathlib import Path

from recordorai_installer.core.detect import (
    Environment,
    detect_environment,
    installer_cache_dir,
    installer_data_dir,
    installer_log_dir,
)


class TestDetectEnvironment:
    def test_returns_a_well_formed_environment(self):
        env = detect_environment()
        assert isinstance(env, Environment)
        assert env.host.os in {"macos", "windows", "linux"}
        assert env.host.arch in {"arm64", "x86_64", "x86", "unknown"}
        assert env.python.version[0] >= 3
        assert isinstance(env.runtimes, list)
        assert len(env.runtimes) == 5  # standalone + 4 host runtimes

    def test_standalone_is_always_present_and_detected(self):
        env = detect_environment()
        standalone = next(r for r in env.runtimes if r.name == "standalone")
        assert standalone.detected is True

    def test_runtime_names_are_canonical(self):
        env = detect_environment()
        names = [r.name for r in env.runtimes]
        assert names == [
            "standalone",
            "openclaw",
            "pi-mono",
            "alice-runtime",
            "hermes",
        ]

    def test_detected_runtimes_property_filters(self, tmp_path):
        env = detect_environment(home=tmp_path)
        # tmp_path has nothing in it, so only standalone is "detected".
        names = [r.name for r in env.detected_runtimes]
        assert "standalone" in names

    def test_picks_up_a_fake_openclaw_install(self, tmp_path):
        (tmp_path / ".openclaw").mkdir()
        (tmp_path / ".openclaw" / "openclaw.json").write_text("{}")
        env = detect_environment(home=tmp_path)
        oc = next(r for r in env.runtimes if r.name == "openclaw")
        assert oc.detected is True
        assert oc.install_path is not None
        assert oc.config_path is not None

    def test_picks_up_existing_recordorai_palace(self, tmp_path):
        (tmp_path / ".recordorai").mkdir()
        env = detect_environment(home=tmp_path)
        assert env.palace_root is not None
        assert ".recordorai" in env.palace_root

    def test_legacy_mempalace_palace_detected(self, tmp_path):
        (tmp_path / ".mempalace").mkdir()
        env = detect_environment(home=tmp_path)
        assert env.palace_root is not None
        assert ".mempalace" in env.palace_root

    def test_apple_silicon_implies_neural_engine(self):
        env = detect_environment()
        if env.host.is_apple_silicon:
            assert env.gpu.has_apple_neural_engine is True
        else:
            assert env.gpu.has_apple_neural_engine is False


class TestPlatformDirs:
    def test_data_cache_log_dirs_are_distinct(self):
        data = installer_data_dir()
        cache = installer_cache_dir()
        logs = installer_log_dir()
        assert isinstance(data, Path)
        assert isinstance(cache, Path)
        assert isinstance(logs, Path)
        assert data != cache
        assert data != logs
        assert cache != logs

    def test_log_dir_is_created_on_call(self):
        logs = installer_log_dir()
        assert logs.exists()
        assert logs.is_dir()
