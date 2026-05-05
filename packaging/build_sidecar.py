#!/usr/bin/env python3
"""Build the recordorai-install Python sidecar and stage it for Tauri.

Tauri's sidecar mechanism expects a binary named
``<original>-<rust-target-triple>(.exe)`` under
``src-tauri/binaries/``. We invoke PyInstaller, then copy the output
to the right name.

Run from the repo root:

    python packaging/build_sidecar.py

Output:

    tauri-app/src-tauri/binaries/recordorai-install-<TRIPLE>(.exe)

where <TRIPLE> matches Rust's host target triple (e.g.
``aarch64-apple-darwin``, ``x86_64-pc-windows-msvc``,
``x86_64-unknown-linux-gnu``).

CI uses this same script — see .github/workflows/release.yml.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "packaging" / "recordorai-install.spec"
DIST_DIR = REPO_ROOT / "dist"
SIDECAR_DIR = REPO_ROOT / "tauri-app" / "src-tauri" / "binaries"


def rust_target_triple() -> str:
    """Best-effort Rust target triple inference, mirroring what
    ``rustc -vV | grep host`` reports.

    The Tauri sidecar suffix MUST match Rust's host triple — Tauri's
    bundler appends ``-<triple>`` to the binary name on
    package-time and falls back to looking for the bare name only on
    macOS.
    """
    sysname = platform.system()
    machine = platform.machine().lower()

    if sysname == "Darwin":
        # arm64 on M-series, x86_64 on Intel.
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-apple-darwin"

    if sysname == "Linux":
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-unknown-linux-gnu"

    if sysname == "Windows":
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-pc-windows-msvc"

    raise RuntimeError(f"Unsupported platform: {sysname} {machine}")


def run_pyinstaller() -> Path:
    """Invoke PyInstaller and return the path to the produced binary."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_PATH),
        "--clean",
        "--noconfirm",
        # PyInstaller resolves relative paths from CWD.
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(REPO_ROOT / "build"),
    ]
    print(f"[build_sidecar] running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)

    exe_name = "recordorai-install.exe" if platform.system() == "Windows" else "recordorai-install"
    out = DIST_DIR / exe_name
    if not out.exists():
        raise FileNotFoundError(f"PyInstaller didn't produce {out}. Check PyInstaller logs above.")
    return out


def stage_for_tauri(produced: Path) -> Path:
    """Copy the PyInstaller output to Tauri's sidecar dir with the
    triple-suffixed name Tauri's bundler expects.
    """
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)

    triple = rust_target_triple()
    suffix = ".exe" if platform.system() == "Windows" else ""
    target_name = f"recordorai-install-{triple}{suffix}"
    target = SIDECAR_DIR / target_name

    if target.exists():
        target.unlink()
    shutil.copy2(produced, target)

    # Tauri also wants the bare name (without triple) symlinked or
    # copied — `tauri build` matches both. Use a copy because Windows
    # symlink permissions are user-hostile.
    bare = SIDECAR_DIR / f"recordorai-install{suffix}"
    if bare.exists():
        bare.unlink()
    shutil.copy2(produced, bare)

    print(f"[build_sidecar] staged: {target}")
    print(f"[build_sidecar] staged: {bare}")
    return target


def main() -> int:
    produced = run_pyinstaller()
    stage_for_tauri(produced)
    print("[build_sidecar] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
