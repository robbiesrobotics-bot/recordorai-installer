# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the recordorai-install CLI/RPC binary.

Produces a single-file executable that contains:

* The recordorai_installer Python package
* The Python interpreter
* All transitive deps (textual, rich, httpx, platformdirs)

Used as the Tauri sidecar — the GUI front-end spawns this binary
with ``--rpc`` and talks JSON-RPC over stdio.

Build (from repo root):

    pyinstaller packaging/recordorai-install.spec --clean --noconfirm

Output:

    dist/recordorai-install                (Linux/macOS)
    dist/recordorai-install.exe            (Windows)

The Tauri sidecar declaration in tauri.conf.json points at the
platform-suffixed copy under tauri-app/src-tauri/binaries/.
"""

from PyInstaller.utils.hooks import collect_submodules


# Collect every recordorai_installer submodule eagerly so dynamic
# imports in adapters/license_clients.get_client() / get_adapter()
# work in the frozen binary. These resolve via importlib at runtime,
# which PyInstaller's static analysis can't see.
_HIDDEN_IMPORTS = sorted(
    set(collect_submodules("recordorai_installer"))
    | {
        # Textual lazily imports its widget set; collect explicitly
        # so the TUI screens render in the frozen build.
        "textual.widgets",
        "textual.containers",
        "textual.screen",
    }
)


a = Analysis(
    ["entrypoint.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the Textual stylesheet — it's loaded relative to the
        # tui.app module at runtime.
        (
            "../src/recordorai_installer/tui/app.tcss",
            "recordorai_installer/tui",
        ),
    ],
    hiddenimports=_HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim the binary by excluding deps we never reach.
        "tkinter",
        "test",
        "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="recordorai-install",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX confuses macOS notarization; leave the binary plain.
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # The TUI needs a real terminal; --rpc reads stdin.
    disable_windowed_traceback=False,
    target_arch=None,  # Use the build host's arch.
    codesign_identity=None,  # Tauri's signing pass handles this.
    entitlements_file=None,
)
