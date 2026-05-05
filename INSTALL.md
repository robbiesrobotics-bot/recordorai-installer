# Installing RecordorAI

This is the **end-user install guide** — what to do after you click
the download link. The operator-side runbook for building and
shipping releases lives in
[`docs/packaging.md`](docs/packaging.md).

---

## TL;DR

| Your OS | Download | Double-click |
|---|---|---|
| **macOS (M-series)** | `RecordorAI_Installer_*_aarch64.dmg` | drag the app to Applications, then right-click → Open |
| **macOS (Intel)** | same `aarch64.dmg` | runs via Rosetta 2 (one-click prompt on first launch — see below) |
| **Windows 10/11** | `RecordorAI_Installer_*_x64-setup.exe` | More info → Run anyway |
| **Ubuntu/Debian** | `RecordorAI_Installer_*_amd64.deb` | `sudo apt install ./that.deb` |
| **Fedora/RHEL** | `RecordorAI_Installer-*.x86_64.rpm` | `sudo dnf install ./that.rpm` |
| **Anything Linux** | `RecordorAI_Installer_*.AppImage` | `chmod +x` and run |

> **Intel Mac users:** v0.1 ships a single arm64 `.dmg`. macOS will
> prompt to install Rosetta 2 the first time you launch the app
> (one click, ~30 seconds). Future Intel-native builds will land
> when the GitHub Actions Intel-Mac runner queue stops being a
> ~15-minute bottleneck per release.

After install, launch `RecordorAI Installer` from your Apps menu (or
run `recordorai-install` from a terminal). The wizard walks you
through 5 screens — Welcome → Edition → Runtime → Features → Install.

---

## During the v0.1 RC period — unsigned builds

While we're waiting for our Apple Developer ID and Windows
codesigning certificate to clear the CA paperwork, the installers
are **functional but unsigned**. Every OS will show a one-time
warning the first time you launch the app. This is normal for
pre-1.0 software; the bypass steps below are the same ones used by
every developer-tools project shipping early access.

The Tauri app's *internal* updater signature (Ed25519) is **always
on** regardless of OS-level codesigning, so updates downloaded
from the GitHub Release are still tamper-checked.

### macOS — "unidentified developer"

When you double-click the `.dmg` and try to open the app:

> "RecordorAI Installer.app" can't be opened because Apple cannot
> check it for malicious software.

**Bypass (one-time):**

1. **Right-click** (or two-finger tap) `RecordorAI Installer.app` in
   Applications → choose **Open**.
2. Click **Open** in the warning dialog. macOS remembers the
   approval; future launches behave normally.

Alternative if step 1 doesn't show "Open":

```bash
sudo xattr -dr com.apple.quarantine '/Applications/RecordorAI Installer.app'
```

### Windows — "Microsoft Defender SmartScreen prevented an unrecognized app from starting"

When you double-click the `.exe`:

> Windows protected your PC.
> Microsoft Defender SmartScreen prevented an unrecognized app from starting.

**Bypass (one-time):**

1. Click **More info** in the SmartScreen dialog.
2. Click **Run anyway** at the bottom.

Alternative — unblock the file before running:

```powershell
Unblock-File -Path "$HOME\Downloads\RecordorAI_Installer_*-setup.exe"
```

### Linux — `.AppImage` won't run

Most distros need:

```bash
chmod +x RecordorAI_Installer_*.AppImage

# If the AppImage uses the older FUSE protocol:
sudo apt install libfuse2          # Debian/Ubuntu
sudo dnf install fuse-libs         # Fedora/RHEL
```

`.deb` and `.rpm` packages don't have this issue — install via
your normal package manager.

---

## What the wizard does

5 screens, ~2 minutes:

1. **Welcome** — shows what the wizard detected on your machine
   (OS, Python, GPU, installed agent runtimes, existing palace).
2. **Edition** — Community (free) vs Pro ($X/month). Paste your
   license key here if you bought Pro.
3. **Runtime** — pick which agent runtime to integrate with:
   Standalone, OpenClaw, pi-mono, alice-runtime, or Hermes Agent.
   The wizard hides runtimes it didn't detect on your machine.
4. **Features** — toggle ingest types (documents always on; audio /
   image / video opt-in because they download multi-GB models).
   Pro features (multi-tenant, sync, smart Observer) appear when
   your license is active.
5. **Review + Install** — see the plan before pressing Install.
   Steps run with full rollback safety; if anything fails, the
   wizard reverses every previous step cleanly.

After install, RecordorAI lives at `~/.recordorai/` and integrates
with your chosen runtime per the adapter's docs.

---

## Re-running the wizard

You can re-run `recordorai-install` any time to:

- Add another runtime (one machine can integrate with multiple).
- Enable a previously-skipped ingest type (e.g. add audio later).
- Switch from Community to Pro after you buy a license.
- Migrate an existing install to a new palace location.

The wizard is fully idempotent — re-running won't duplicate steps
or overwrite working configs.

---

## Uninstalling

```bash
recordorai-install --uninstall    # reverses the wizard's actions
```

The `--uninstall` path:

- Removes RecordorAI's hooks and config from the chosen runtime.
- Restores any backup configs the wizard saved during install.
- Leaves your palace data (`~/.recordorai/`) intact unless you
  pass `--purge` (we don't delete your data without explicit
  consent).

---

## Need help?

- File an issue at <https://github.com/RecordorAI/recordorai-installer/issues>
- Pro support customers: support@recordorai.com (link in your
  Lemon Squeezy receipt)
