"""Environment detection — runs once at wizard startup.

The wizard uses :class:`Environment` to decide which screens to show,
which adapters are eligible, and what defaults to pre-fill.

Pure-stdlib + ``platformdirs``; no network calls, no privileged
operations. Safe to run on a locked-down machine.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

# ──────────────────────────────────────────────────────────────────────────
# Public dataclasses
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HostInfo:
    """Things about the user's machine that don't change session-to-session."""

    os: str  # "macos" | "windows" | "linux"
    arch: str  # "arm64" | "x86_64" | "x86" | other
    os_version: str  # e.g. "14.4" on macOS, "11.22631" on Win
    is_apple_silicon: bool


@dataclass(frozen=True)
class PythonInfo:
    """The Python the installer is running under."""

    executable: str
    version: tuple[int, int, int]  # (3, 11, 5) etc.
    is_venv: bool
    site_packages: str


@dataclass(frozen=True)
class GPUInfo:
    """What acceleration is available for RecordorAI's optional models.

    Multimodal ingest (audio/image/video) benefits from GPU but works
    on CPU; CE rerank benefits from ANE on Apple Silicon.
    """

    has_apple_neural_engine: bool  # M-series Macs only
    has_cuda: bool  # NVIDIA via PyTorch
    has_rocm: bool  # AMD via PyTorch
    cuda_version: str | None = None


@dataclass(frozen=True)
class RuntimeInfo:
    """A detected agent runtime that RecordorAI can integrate with."""

    name: str  # "openclaw" | "pi-mono" | "alice-runtime" | "hermes" | "standalone"
    detected: bool
    install_path: str | None = None
    version: str | None = None
    config_path: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class Environment:
    """Everything detect.py learned about the user's machine."""

    host: HostInfo
    python: PythonInfo
    gpu: GPUInfo
    runtimes: list[RuntimeInfo] = field(default_factory=list)
    existing_recordorai: str | None = None  # version string if installed
    palace_root: str | None = None  # ~/.recordorai/ if it exists

    @property
    def detected_runtimes(self) -> list[RuntimeInfo]:
        """Runtimes that are actually installed on this machine. Always
        includes 'standalone' since that's a no-runtime install path."""
        return [r for r in self.runtimes if r.detected]


# ──────────────────────────────────────────────────────────────────────────
# Host detection
# ──────────────────────────────────────────────────────────────────────────


def _detect_host() -> HostInfo:
    """Determine OS, architecture, version, and Apple-Silicon flag."""
    sysname = platform.system()
    if sysname == "Darwin":
        os_name = "macos"
        os_version = platform.mac_ver()[0] or platform.release()
    elif sysname == "Windows":
        os_name = "windows"
        os_version = platform.version()
    elif sysname == "Linux":
        os_name = "linux"
        os_version = platform.release()
    else:
        os_name = sysname.lower()
        os_version = platform.release()

    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("i386", "i686", "x86"):
        arch = "x86"
    else:
        arch = machine or "unknown"

    is_apple = os_name == "macos" and arch == "arm64"

    return HostInfo(
        os=os_name,
        arch=arch,
        os_version=os_version,
        is_apple_silicon=is_apple,
    )


# ──────────────────────────────────────────────────────────────────────────
# Python detection
# ──────────────────────────────────────────────────────────────────────────


def _detect_python() -> PythonInfo:
    """Capture the running Python — version + venv state + site-packages."""
    info = sys.version_info
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    # Best-effort site-packages — handles both venv and system Pythons.
    try:
        import site

        site_dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
        site_path = site_dirs[0] if site_dirs else site.getusersitepackages()
    except (ImportError, AttributeError):
        site_path = ""

    return PythonInfo(
        executable=sys.executable,
        version=(info.major, info.minor, info.micro),
        is_venv=in_venv,
        site_packages=site_path,
    )


# ──────────────────────────────────────────────────────────────────────────
# GPU / accelerator detection
# ──────────────────────────────────────────────────────────────────────────


def _detect_gpu(host: HostInfo) -> GPUInfo:
    """Best-effort acceleration check.

    We don't import torch here — it's heavy and may not be installed.
    Instead we probe via shell commands and platform hints.
    """
    has_ane = host.is_apple_silicon  # All M-series Macs have ANE.

    has_cuda = False
    has_rocm = False
    cuda_version: str | None = None

    # CUDA: check for nvidia-smi.
    if host.os in ("linux", "windows"):
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                out = subprocess.run(
                    [nvidia_smi, "--query-gpu=driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if out.returncode == 0 and out.stdout.strip():
                    has_cuda = True
                    cuda_version = out.stdout.strip().splitlines()[0]
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass

    # ROCm: check for rocminfo.
    if host.os == "linux":
        if shutil.which("rocminfo"):
            has_rocm = True

    return GPUInfo(
        has_apple_neural_engine=has_ane,
        has_cuda=has_cuda,
        has_rocm=has_rocm,
        cuda_version=cuda_version,
    )


# ──────────────────────────────────────────────────────────────────────────
# Runtime detection — one probe per supported agent runtime
# ──────────────────────────────────────────────────────────────────────────


def _probe_openclaw(home: Path) -> RuntimeInfo:
    """OpenClaw lives at ~/.openclaw/ on macOS/Linux and
    %USERPROFILE%\\.openclaw on Windows."""
    root = home / ".openclaw"
    config = root / "openclaw.json"
    detected = root.is_dir()

    version: str | None = None
    if detected:
        # OpenClaw embeds a version in package.json or similar; look for
        # the closest known marker.
        for candidate in (root / "version.txt", root / "package.json"):
            if candidate.exists():
                try:
                    text = candidate.read_text(encoding="utf-8")
                    if candidate.name == "package.json":
                        import json

                        data = json.loads(text)
                        version = data.get("version")
                    else:
                        version = text.strip().splitlines()[0]
                    break
                except (OSError, ValueError, ImportError):
                    pass

    return RuntimeInfo(
        name="openclaw",
        detected=detected,
        install_path=str(root) if detected else None,
        version=version,
        config_path=str(config) if config.exists() else None,
        notes="" if detected else "Install from openclaw.com if you want OpenClaw integration.",
    )


def _probe_pi_mono(home: Path) -> RuntimeInfo:
    """pi-mono is an npm package family (badlogic/pi-mono). We detect
    it via a global npm check or local node_modules."""
    npm = shutil.which("npm")
    detected = False
    install_path: str | None = None
    version: str | None = None

    if npm:
        try:
            out = subprocess.run(
                [npm, "list", "-g", "--depth=0", "--json"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if out.returncode == 0:
                import json

                data = json.loads(out.stdout or "{}")
                deps = data.get("dependencies", {}) or {}
                # Look for any @mariozechner/pi-* or pi-mono package.
                pi_pkgs = {
                    k: v for k, v in deps.items() if "pi-" in k or k.startswith("@mariozechner/")
                }
                if pi_pkgs:
                    detected = True
                    first = next(iter(pi_pkgs.values()))
                    version = (first or {}).get("version")
                    install_path = data.get("path") or ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError, ImportError):
            pass

    return RuntimeInfo(
        name="pi-mono",
        detected=detected,
        install_path=install_path,
        version=version,
        notes="" if detected else "Install with `npm i -g @mariozechner/pi-coding-agent`.",
    )


def _probe_alice_runtime(home: Path) -> RuntimeInfo:
    """alice-runtime is a Bun gateway under development; the convention
    is to install it under ~/.alice/ or via `alice` on PATH."""
    detected = False
    install_path: str | None = None
    version: str | None = None

    alice_bin = shutil.which("alice")
    if alice_bin:
        detected = True
        install_path = str(Path(alice_bin).parent)
        try:
            out = subprocess.run(
                [alice_bin, "--version"], capture_output=True, text=True, timeout=3
            )
            if out.returncode == 0:
                version = out.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    if not detected:
        alt = home / ".alice"
        if alt.is_dir():
            detected = True
            install_path = str(alt)

    return RuntimeInfo(
        name="alice-runtime",
        detected=detected,
        install_path=install_path,
        version=version,
        notes=""
        if detected
        else "alice-runtime is in early development; integration is best-effort.",
    )


def _probe_hermes(home: Path) -> RuntimeInfo:
    """Hermes Agent (NousResearch) is a Python package; check for the
    `hermes` CLI on PATH or a hermes config under ~/.hermes/."""
    detected = False
    install_path: str | None = None
    version: str | None = None

    hermes_bin = shutil.which("hermes") or shutil.which("hermes-agent")
    if hermes_bin:
        detected = True
        install_path = str(Path(hermes_bin).parent)
        try:
            out = subprocess.run(
                [hermes_bin, "--version"], capture_output=True, text=True, timeout=3
            )
            if out.returncode == 0:
                version = out.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    if not detected:
        cfg = home / ".hermes"
        if cfg.is_dir():
            detected = True
            install_path = str(cfg)

    return RuntimeInfo(
        name="hermes",
        detected=detected,
        install_path=install_path,
        version=version,
        notes="" if detected else "Install Hermes Agent from github.com/NousResearch/hermes-agent.",
    )


def _probe_standalone() -> RuntimeInfo:
    """The 'standalone' runtime is always available — it's the no-runtime
    install path (CLI on PATH, Python API, MCP server)."""
    return RuntimeInfo(
        name="standalone",
        detected=True,
        notes="Default — no host runtime required.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Existing RecordorAI detection
# ──────────────────────────────────────────────────────────────────────────


def _detect_existing_recordorai(home: Path) -> tuple[str | None, str | None]:
    """Returns (version, palace_root) if a prior recordorai install is found.

    Used by the wizard to offer 'upgrade' vs 'fresh install' paths.
    """
    version: str | None = None
    try:
        # If recordorai is importable in the current Python, capture its version.
        import recordorai  # type: ignore[import-not-found]

        version = getattr(recordorai, "__version__", None)
    except ImportError:
        pass

    palace_root: str | None = None
    candidate = home / ".recordorai"
    if candidate.is_dir():
        palace_root = str(candidate)
    else:
        # Legacy mempalace path.
        legacy = home / ".mempalace"
        if legacy.is_dir():
            palace_root = str(legacy)

    return version, palace_root


# ──────────────────────────────────────────────────────────────────────────
# Top-level entry
# ──────────────────────────────────────────────────────────────────────────


def detect_environment(home: Path | None = None) -> Environment:
    """Run every detector and return a frozen :class:`Environment`.

    Parameters
    ----------
    home:
        Optional override for the user's home directory — used by tests
        to point at a temp dir. Defaults to ``Path.home()``.
    """
    home = home or Path.home()

    host = _detect_host()
    python = _detect_python()
    gpu = _detect_gpu(host)
    existing_version, palace_root = _detect_existing_recordorai(home)

    runtimes = [
        _probe_standalone(),
        _probe_openclaw(home),
        _probe_pi_mono(home),
        _probe_alice_runtime(home),
        _probe_hermes(home),
    ]

    return Environment(
        host=host,
        python=python,
        gpu=gpu,
        runtimes=runtimes,
        existing_recordorai=existing_version,
        palace_root=palace_root,
    )


# ──────────────────────────────────────────────────────────────────────────
# Convenience for the wizard
# ──────────────────────────────────────────────────────────────────────────


def installer_data_dir() -> Path:
    """OS-aware location for installer state (logs, license cache, etc.).

    Mac:    ~/Library/Application Support/RecordorAI Installer
    Linux:  ~/.local/share/recordorai-installer
    Win:    %LOCALAPPDATA%\\RecordorAI\\Installer
    """
    return Path(platformdirs.user_data_dir("recordorai-installer", "RecordorAI"))


def installer_cache_dir() -> Path:
    """OS-aware cache for downloaded artifacts (e.g. model files)."""
    return Path(platformdirs.user_cache_dir("recordorai-installer", "RecordorAI"))


def installer_log_dir() -> Path:
    """OS-aware logs directory; the install transcript lives here."""
    base = Path(platformdirs.user_log_dir("recordorai-installer", "RecordorAI"))
    base.mkdir(parents=True, exist_ok=True)
    return base
