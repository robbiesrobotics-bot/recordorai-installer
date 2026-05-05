#!/usr/bin/env python3
"""Build the Tauri auto-updater manifest (latest.json).

The Tauri updater plugin polls a JSON manifest at the URL configured
in tauri.conf.json's plugins.updater.endpoints. The manifest tells
Tauri which version is current + where to download the per-platform
update artifact + the Ed25519 signature of that artifact.

This script reads the bundle artifacts produced by the Release CI
workflow and assembles the manifest.

Schema (Tauri v2):

    {
      "version": "0.1.0",
      "notes": "Release notes for this version",
      "pub_date": "2026-05-05T00:00:00Z",
      "platforms": {
        "darwin-aarch64": {
          "signature": "<base64 Ed25519 sig>",
          "url": "https://github.com/.../RecordorAI_Installer_aarch64.app.tar.gz"
        },
        "darwin-x86_64":  { "signature": "...", "url": "..." },
        "linux-x86_64":   { "signature": "...", "url": "..." },
        "windows-x86_64": { "signature": "...", "url": "..." }
      }
    }

Tauri ships a separate `*.sig` file alongside each bundle target
when TAURI_SIGNING_PRIVATE_KEY is set in CI. We read those here.

Usage (from CI):

    python packaging/build_updater_manifest.py \\
        --tag v0.1.0 \\
        --artifacts artifacts/ \\
        --out latest.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

# Tauri's per-platform update file extensions (the .tar.gz / .nsis.zip
# variants are what tauri-update expects, NOT the .dmg / .msi
# wrapper).
_PLATFORM_PATTERNS = {
    "darwin-aarch64": re.compile(r".*aarch64.*\.app\.tar\.gz$", re.IGNORECASE),
    "darwin-x86_64": re.compile(r".*x86_64.*\.app\.tar\.gz$", re.IGNORECASE),
    "linux-x86_64": re.compile(r".*\.AppImage$", re.IGNORECASE),
    "windows-x86_64": re.compile(r".*\.nsis\.zip$", re.IGNORECASE),
}


def _find_artifact(artifacts_dir: Path, pattern: re.Pattern) -> Path | None:
    candidates = [p for p in artifacts_dir.rglob("*") if pattern.match(p.name)]
    return candidates[0] if candidates else None


def _read_signature(artifact: Path) -> str:
    """Tauri writes the Ed25519 signature to <artifact>.sig as base64.
    If the sig file is missing (unsigned dev build), return an empty
    string so the manifest is still well-formed.
    """
    sig_path = artifact.with_suffix(artifact.suffix + ".sig")
    if not sig_path.exists():
        # Fallback for some Tauri targets that emit .sig next to the
        # base file without doubling the extension.
        alt = artifact.parent / (artifact.name + ".sig")
        if alt.exists():
            sig_path = alt
        else:
            return ""
    return sig_path.read_text().strip()


def _release_url(repo: str, tag: str, name: str) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{name}"


def build_manifest(
    *,
    tag: str,
    artifacts_dir: Path,
    repo: str,
    notes: str,
) -> dict:
    version = tag.lstrip("v")
    pub_date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    platforms: dict[str, dict[str, str]] = {}
    for platform_key, pattern in _PLATFORM_PATTERNS.items():
        artifact = _find_artifact(artifacts_dir, pattern)
        if not artifact:
            print(
                f"[manifest] WARN: no artifact for {platform_key}; "
                f"skipping. Pattern: {pattern.pattern}",
                file=sys.stderr,
            )
            continue
        platforms[platform_key] = {
            "signature": _read_signature(artifact),
            "url": _release_url(repo, tag, artifact.name),
        }

    return {
        "version": version,
        "notes": notes,
        "pub_date": pub_date,
        "platforms": platforms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Tauri updater manifest")
    parser.add_argument("--tag", required=True, help="Release tag, e.g. v0.1.0")
    parser.add_argument("--artifacts", required=True, type=Path, help="Path to bundles dir")
    parser.add_argument("--out", required=True, type=Path, help="Output manifest path")
    parser.add_argument(
        "--repo",
        default="RecordorAI/recordorai-installer",
        help="GitHub owner/repo for the download URLs",
    )
    parser.add_argument(
        "--notes",
        default="See the GitHub release page for full notes.",
        help="Free-form release notes shown to the user during update",
    )
    args = parser.parse_args()

    manifest = build_manifest(
        tag=args.tag,
        artifacts_dir=args.artifacts,
        repo=args.repo,
        notes=args.notes,
    )
    args.out.write_text(json.dumps(manifest, indent=2))
    print(f"[manifest] wrote {args.out}")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
