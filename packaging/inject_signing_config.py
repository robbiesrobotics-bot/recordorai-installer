#!/usr/bin/env python3
"""Inject signing config into tauri.conf.json based on present env vars.

The base tauri.conf.json ships without signing fields so unsigned
builds (no certs available) work out of the box. CI calls this script
before `tauri build`; if the relevant secret env vars are set, the
matching signing fields get patched in. Otherwise the build proceeds
unsigned.

This avoids the previous trap where placeholder strings like
``$APPLE_SIGNING_IDENTITY`` would be passed verbatim to ``codesign
-s ""`` and fail with "specified item could not be found in the
keychain". Tauri does NOT do env var interpolation in its JSON
config — the interpolation has to happen in the workflow.

Reads from env:

    APPLE_SIGNING_IDENTITY            macOS Developer ID identity
    APPLE_PROVIDER_SHORT_NAME         macOS team short name (notarytool)
    WINDOWS_CERTIFICATE_THUMBPRINT    Windows codesign cert SHA1
    TAURI_UPDATER_PUBKEY              Ed25519 public key for updater

Run from the repo root:

    python packaging/inject_signing_config.py

The script is idempotent — running with no env vars set is a no-op
(yields the same config that was already on disk).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path("tauri-app/src-tauri/tauri.conf.json")


def _set_path(d: dict, keys: list[str], value) -> None:
    """Set d[keys[0]][keys[1]]...[keys[-1]] = value, creating dicts
    along the way as needed.
    """
    cur = d
    for k in keys[:-1]:
        cur = cur.setdefault(k, {})
    cur[keys[-1]] = value


def _get(env: str) -> str | None:
    """Return the env var if set + non-empty, else None."""
    v = os.environ.get(env, "").strip()
    return v or None


def main() -> int:
    if not CONFIG_PATH.exists():
        print(f"error: {CONFIG_PATH} not found", file=sys.stderr)
        return 1

    config = json.loads(CONFIG_PATH.read_text())

    changes: list[str] = []

    apple_identity = _get("APPLE_SIGNING_IDENTITY")
    if apple_identity:
        _set_path(config, ["bundle", "macOS", "signingIdentity"], apple_identity)
        changes.append(f"bundle.macOS.signingIdentity = {apple_identity!r}")
        provider = _get("APPLE_PROVIDER_SHORT_NAME") or _get("APPLE_TEAM_ID")
        if provider:
            _set_path(
                config,
                ["bundle", "macOS", "providerShortName"],
                provider,
            )
            changes.append(f"bundle.macOS.providerShortName = {provider!r}")
        # Entitlements file lives alongside tauri.conf.json; only set
        # if the cert is available, otherwise Tauri shouldn't expect it.
        _set_path(
            config,
            ["bundle", "macOS", "entitlements"],
            "entitlements.plist",
        )
        changes.append("bundle.macOS.entitlements = 'entitlements.plist'")

    win_thumb = _get("WINDOWS_CERTIFICATE_THUMBPRINT")
    if win_thumb:
        _set_path(
            config,
            ["bundle", "windows", "certificateThumbprint"],
            win_thumb,
        )
        _set_path(
            config,
            ["bundle", "windows", "digestAlgorithm"],
            "sha256",
        )
        _set_path(
            config,
            ["bundle", "windows", "timestampUrl"],
            "http://timestamp.digicert.com",
        )
        changes.append(f"bundle.windows.certificateThumbprint = {win_thumb!r}")

    pubkey = _get("TAURI_UPDATER_PUBKEY")
    if pubkey:
        _set_path(config, ["plugins", "updater", "pubkey"], pubkey)
        changes.append(f"plugins.updater.pubkey = <{len(pubkey)} chars>")

    CONFIG_PATH.write_text(json.dumps(config, indent=2))

    if changes:
        print("[inject_signing_config] applied:")
        for c in changes:
            print(f"  - {c}")
    else:
        print(
            "[inject_signing_config] no signing secrets detected — "
            "config left unchanged (unsigned build path)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
