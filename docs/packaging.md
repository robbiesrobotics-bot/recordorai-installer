# Packaging & signing — operator runbook

Sprint 4 ships the engineering side of native installer packaging:

* `packaging/recordorai-install.spec` — PyInstaller spec for the
  Python sidecar binary
* `packaging/build_sidecar.py` — local + CI build script
* `packaging/build_updater_manifest.py` — Tauri auto-updater manifest
* `tauri-app/src-tauri/tauri.conf.json` — bundle targets, sidecar
  declaration, signing placeholders
* `.github/workflows/release.yml` — tag-push CI matrix that produces
  `.dmg` / `.msi` / `.nsis` / `.deb` / `.rpm` / `.AppImage` for every
  supported OS and uploads them to a GitHub Release

What this **doesn't** ship is the certificates — those are paperwork
the human operator has to acquire once and feed to the CI as secrets.
This document is the one-time bootstrap.

---

## Local smoke build (no certs required)

You can produce unsigned installers on your own machine before
spending money on certs. This is the fastest way to verify the
pipeline works end-to-end.

```bash
# 1. Build the Python sidecar locally
pip install pyinstaller
python packaging/build_sidecar.py

# 2. Build the Tauri app with the sidecar embedded
cd tauri-app
bun install --frozen-lockfile
bun x tauri build
```

Output lives under
`tauri-app/src-tauri/target/release/bundle/{dmg,msi,nsis,deb,rpm,appimage}/`.

The `.dmg` / `.msi` will be **unsigned** — your OS will warn the
user on first launch ("unidentified developer" / SmartScreen). For
production releases, finish the cert setup below.

---

## 1. Apple Developer ID (macOS — required)

**Cost:** $99/year, individual or organization.
**Time:** 1-3 days for Apple to approve the enrollment.

### Steps

1. **Enroll** at <https://developer.apple.com/programs/enroll/>.
2. Sign in to <https://developer.apple.com/account/> → Certificates →
   click `+` → choose **Developer ID Application**.
3. Generate a CSR (Certificate Signing Request) on your Mac:

   - Open Keychain Access → menu Keychain Access → Certificate
     Assistant → Request a Certificate from a Certificate Authority.
   - Email: your Apple ID. Name: anything. Saved to disk.
   - Upload the resulting `.certSigningRequest` to Apple.

4. Apple emits a `.cer`. Double-click it to import into Keychain
   Access.
5. Find the cert in Keychain Access → My Certificates → right-click
   → **Export…** → save as `developer-id.p12`. Set a password.
6. Find the **Team ID** at <https://developer.apple.com/account/#MembershipDetailsCard>
   (10-character alphanumeric).
7. Create an **app-specific password** at <https://appleid.apple.com/>
   → Sign-In and Security → App-Specific Passwords. Label it
   "RecordorAI Notarization".

### Convert the .p12 to base64 for GitHub Secrets

```bash
base64 -i developer-id.p12 | pbcopy   # macOS
base64 developer-id.p12 -w 0          # Linux
```

### Set the GitHub Actions secrets

In `Settings → Secrets and variables → Actions` on the repo:

| secret | value |
|---|---|
| `APPLE_CERTIFICATE` | base64 contents of `developer-id.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | password from step 5 |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Your Name (TEAMID)` — copy verbatim from Keychain Access |
| `APPLE_ID` | your Apple ID email |
| `APPLE_PASSWORD` | the app-specific password from step 7 |
| `APPLE_TEAM_ID` | the 10-char team ID from step 6 |

Tauri's bundler handles the rest:
- `codesign` runs against the `Developer ID Application` cert
- `notarytool` submits the bundle to Apple
- `stapler` staples the notarization ticket

The user double-clicks the `.dmg`, Gatekeeper reads the staple, and
the app opens without warnings.

---

## 2. Windows codesigning cert

**Cost:** $80–$300/year (regular) or $300–$700/year (EV).
**Time:** 1-7 days for the CA to validate your identity.

### Choose: regular cert vs EV cert

| | Regular OV cert | EV cert |
|---|---|---|
| Cost | $80–$300/yr | $300–$700/yr |
| First-run SmartScreen warning | YES, until reputation accumulates | NO, immediate trust |
| Hardware token required | No | Yes (USB key, FIPS 140-2) |
| CI signing | Easy (.pfx file) | Hard (need KSP / cloud signing — Azure Key Vault, DigiCert KeyLocker, etc.) |

**My pick for v0.1: regular OV cert from Sectigo (~$100/yr via SSL.com
or DigiCert).** The SmartScreen warning sucks but goes away after
~3000 user installs build reputation. EV is worth it later when scale
warrants the operational complexity.

### Steps (regular OV cert)

1. Buy from Sectigo, DigiCert, SSL.com, etc. They'll validate your
   identity (business listing or photo ID) over a few days.
2. CA emails you a cert. Import into Windows: double-click the
   `.cer` file → Install → Personal store.
3. Export with the private key:
   - `certmgr.msc` → Personal → Certificates → right-click → Export
   - "Yes, export the private key" → PFX format
   - Set a password
4. Get the SHA1 thumbprint:
   - In `certmgr.msc`, double-click the cert → Details tab →
     scroll to "Thumbprint" → copy the hex string (40 chars)
5. base64-encode the .pfx for the secret:

   ```bash
   base64 cert.pfx -w 0 > cert.pfx.b64
   ```

### Set the GitHub Actions secrets

| secret | value |
|---|---|
| `WINDOWS_CERTIFICATE` | base64 contents of the .pfx |
| `WINDOWS_CERTIFICATE_PASSWORD` | password from step 3 |
| `WINDOWS_CERTIFICATE_THUMBPRINT` | thumbprint from step 4 |

---

## 3. Tauri auto-update signing key

The Tauri updater verifies downloaded updates with an Ed25519
signature. The key is yours, not anyone else's — generated once,
embedded in the app via `tauri.conf.json`'s
`plugins.updater.pubkey`.

### Generate

```bash
cd tauri-app
bun x tauri signer generate -w ~/.tauri/recordorai-updater-key
```

That writes:
- `~/.tauri/recordorai-updater-key` (PRIVATE — never commit)
- `~/.tauri/recordorai-updater-key.pub` (public — paste into config)

### Wire up

1. In `tauri-app/src-tauri/tauri.conf.json`, replace
   `"$TAURI_UPDATER_PUBKEY"` with the contents of the `.pub` file
   (a base64 string). Commit the config; the public key is
   intentionally public.

2. Set the GitHub Actions secret:

   | secret | value |
   |---|---|
   | `TAURI_SIGNING_PRIVATE_KEY` | contents of the private key file |
   | `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | the passphrase you set during generate (or empty) |

CI signs every bundle artifact with the private key, producing
`<bundle>.sig` files that the updater manifest references.

---

## 4. Linux — no signing required

`.deb` and `.rpm` packages don't need to be signed (most distros
will ask the user to acknowledge unsigned packages but won't block
them). AppImage is also unsigned by convention.

If you want to sign for Debian / Ubuntu's APT system, that's a
separate process (set up a GPG key + a hosted APT repo). Out of
scope for v0.1.

---

## 5. Cutting a release

Once the secrets are set:

```bash
# 1. Bump the version in pyproject.toml + src/recordorai_installer/version.py
#    + tauri-app/src-tauri/tauri.conf.json + tauri-app/package.json.
#    All four MUST agree.

# 2. Tag the commit
git tag v0.1.0
git push origin v0.1.0
```

CI fires, the matrix runs, and within ~30 minutes you have:

- `RecordorAI_Installer_x.y.z_aarch64.dmg` (Mac M-series)
- `RecordorAI_Installer_x.y.z_x64.dmg` (Mac Intel)
- `RecordorAI_Installer_x.y.z_x64-setup.exe` (Windows)
- `RecordorAI_Installer_x.y.z_amd64.deb` (Debian/Ubuntu)
- `RecordorAI_Installer-x.y.z-1.x86_64.rpm` (Fedora/RHEL)
- `RecordorAI_Installer_x.y.z_amd64.AppImage` (universal Linux)
- `latest.json` (Tauri updater manifest)

attached to the GitHub Release. Existing installs auto-update on
next launch via the embedded updater.

---

## 6. Dry-run a release without a tag

In `Actions → Release → Run workflow`, the workflow dispatches with
a `tag_override` input. The workflow runs end-to-end but doesn't
publish a GitHub Release at the end — useful for verifying signing
works before committing to a real version number.

---

## Troubleshooting

### macOS: "binary is damaged and can't be opened"

The notarization didn't staple. Common causes:

* `APPLE_TEAM_ID` mismatch between the `.p12` cert and the
  `tauri.conf.json` `signingIdentity` / `providerShortName`.
* `entitlements.plist` missing or has invalid keys.
* `notarytool` failed silently — check the GitHub Actions log for
  the JSON response from Apple.

### Windows: "publisher unknown" / SmartScreen warning

Your OV cert is too new — Microsoft's reputation system needs
~3000 installs before SmartScreen trusts it. Workarounds:

* Submit the cert for "extended validation" to Microsoft (free, ~3
  weeks).
* Buy an EV cert (instant trust but ~$300/yr more + hardware token).

### Linux: AppImage won't run

The user needs `libfuse2`. Either:

* Document this in the install instructions ("install
  `libfuse2`").
* Switch to `bundleMediaFramework: true` in `tauri.conf.json` to
  bundle FUSE inside the AppImage (~10 MB larger).

---

## Cost summary

| item | one-time | recurring |
|---|---|---|
| Apple Developer ID | — | $99/yr |
| Windows OV codesigning cert | — | ~$100/yr |
| Tauri updater key | — | $0 |
| GitHub Actions CI minutes | — | free for public repos |
| **TOTAL** | **$0** | **~$200/yr** |

That's the all-in floor for a signed, notarized, auto-updating
multi-platform installer. Add Stripe Tax (~0.5% on transactions) if
you go the Stripe-direct path; Lemon Squeezy bundles it.
