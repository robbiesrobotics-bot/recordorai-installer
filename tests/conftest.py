"""Shared pytest fixtures for the installer suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from recordorai_installer.core.detect import (
    Environment,
    GPUInfo,
    HostInfo,
    PythonInfo,
    RuntimeInfo,
)


@pytest.fixture
def fake_env_macos_arm64(tmp_path: Path) -> Environment:
    """Apple Silicon Mac with no host runtimes installed."""
    return Environment(
        host=HostInfo(os="macos", arch="arm64", os_version="14.4", is_apple_silicon=True),
        python=PythonInfo(
            executable="/usr/bin/python3",
            version=(3, 11, 5),
            is_venv=False,
            site_packages=str(tmp_path / "site-packages"),
        ),
        gpu=GPUInfo(
            has_apple_neural_engine=True,
            has_cuda=False,
            has_rocm=False,
        ),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True, notes="default"),
            RuntimeInfo(name="openclaw", detected=False),
            RuntimeInfo(name="pi-mono", detected=False),
            RuntimeInfo(name="alice-runtime", detected=False),
            RuntimeInfo(name="hermes", detected=False),
        ],
        existing_recordorai=None,
        palace_root=None,
    )


@pytest.fixture
def fake_env_linux_x86(tmp_path: Path) -> Environment:
    """Linux x86_64 with no GPU acceleration."""
    return Environment(
        host=HostInfo(os="linux", arch="x86_64", os_version="6.5.0", is_apple_silicon=False),
        python=PythonInfo(
            executable="/usr/bin/python3",
            version=(3, 11, 5),
            is_venv=False,
            site_packages=str(tmp_path / "site-packages"),
        ),
        gpu=GPUInfo(
            has_apple_neural_engine=False,
            has_cuda=False,
            has_rocm=False,
        ),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True),
            RuntimeInfo(name="openclaw", detected=False),
            RuntimeInfo(name="pi-mono", detected=False),
            RuntimeInfo(name="alice-runtime", detected=False),
            RuntimeInfo(name="hermes", detected=False),
        ],
        existing_recordorai=None,
        palace_root=None,
    )


@pytest.fixture
def fake_env_with_openclaw(tmp_path: Path) -> Environment:
    """Mac with an OpenClaw install detected."""
    openclaw_root = tmp_path / ".openclaw"
    openclaw_root.mkdir()
    (openclaw_root / "openclaw.json").write_text("{}")
    return Environment(
        host=HostInfo(os="macos", arch="arm64", os_version="14.4", is_apple_silicon=True),
        python=PythonInfo(
            executable="/usr/bin/python3",
            version=(3, 11, 5),
            is_venv=False,
            site_packages=str(tmp_path / "site-packages"),
        ),
        gpu=GPUInfo(
            has_apple_neural_engine=True,
            has_cuda=False,
            has_rocm=False,
        ),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True),
            RuntimeInfo(
                name="openclaw",
                detected=True,
                install_path=str(openclaw_root),
                version="3.3.0",
                config_path=str(openclaw_root / "openclaw.json"),
            ),
            RuntimeInfo(name="pi-mono", detected=False),
            RuntimeInfo(name="alice-runtime", detected=False),
            RuntimeInfo(name="hermes", detected=False),
        ],
        existing_recordorai="3.3.2",
        palace_root=str(tmp_path / ".recordorai"),
    )
