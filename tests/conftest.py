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


def _mac_arm_pythoninfo(tmp_path: Path) -> PythonInfo:
    return PythonInfo(
        executable="/usr/bin/python3",
        version=(3, 11, 5),
        is_venv=False,
        site_packages=str(tmp_path / "site-packages"),
    )


def _mac_arm_host() -> HostInfo:
    return HostInfo(os="macos", arch="arm64", os_version="14.4", is_apple_silicon=True)


def _ane_gpu() -> GPUInfo:
    return GPUInfo(has_apple_neural_engine=True, has_cuda=False, has_rocm=False)


@pytest.fixture
def fake_env_with_hermes(tmp_path: Path) -> Environment:
    """Mac with Hermes Agent detected at ~/.hermes/."""
    hermes_root = tmp_path / ".hermes"
    hermes_root.mkdir()
    return Environment(
        host=_mac_arm_host(),
        python=_mac_arm_pythoninfo(tmp_path),
        gpu=_ane_gpu(),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True),
            RuntimeInfo(name="openclaw", detected=False),
            RuntimeInfo(name="pi-mono", detected=False),
            RuntimeInfo(name="alice-runtime", detected=False),
            RuntimeInfo(
                name="hermes",
                detected=True,
                install_path=str(hermes_root),
                version="0.10.0",
            ),
        ],
        existing_recordorai=None,
        palace_root=None,
    )


@pytest.fixture
def fake_env_with_pi_mono(tmp_path: Path) -> Environment:
    """Mac with pi-mono detected via npm global."""
    return Environment(
        host=_mac_arm_host(),
        python=_mac_arm_pythoninfo(tmp_path),
        gpu=_ane_gpu(),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True),
            RuntimeInfo(name="openclaw", detected=False),
            RuntimeInfo(
                name="pi-mono",
                detected=True,
                install_path="/usr/local/lib/node_modules",
                version="1.0.0",
            ),
            RuntimeInfo(name="alice-runtime", detected=False),
            RuntimeInfo(name="hermes", detected=False),
        ],
        existing_recordorai=None,
        palace_root=None,
    )


@pytest.fixture
def fake_env_with_alice_runtime(tmp_path: Path) -> Environment:
    """Mac with alice-runtime detected at ~/.alice/."""
    alice_root = tmp_path / ".alice"
    alice_root.mkdir()
    return Environment(
        host=_mac_arm_host(),
        python=_mac_arm_pythoninfo(tmp_path),
        gpu=_ane_gpu(),
        runtimes=[
            RuntimeInfo(name="standalone", detected=True),
            RuntimeInfo(name="openclaw", detected=False),
            RuntimeInfo(name="pi-mono", detected=False),
            RuntimeInfo(
                name="alice-runtime",
                detected=True,
                install_path=str(alice_root),
                version=None,
            ),
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
