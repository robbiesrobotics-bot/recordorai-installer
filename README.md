# RecordorAI Installer

Cross-platform installer + integration wizard for [RecordorAI](https://github.com/RecordorAI/recordorai) — the local-first AI memory system.

Two front-ends, one core:

* **TUI** (Textual) for developers — `recordorai-install` after `pip install`
* **Tauri GUI** for end users — native installer download (Mac/Win/Linux)

Both share the same Python core (`recordorai_installer.core.*`), which:

1. **Detects** the user's environment (OS, arch, Python, GPU, installed agent runtimes)
2. **Plans** the install based on user choices (which runtime, which features)
3. **Executes** the plan with rollback safety
4. **Integrates** with the chosen runtime — Standalone, OpenClaw, pi-mono, Alice-runtime, or Hermes Agent

## Open-core

| Free (Community) | Pro (monthly subscription) |
|---|---|
| Full retrieval + ingest stack | Multi-tenant (per-user palaces + ACLs) |
| All five runtime integrations | Cross-device sync (encrypted) |
| Single-user, single-machine | Smart Observer (LLM-augmented capsule generation) |
| Community support | Priority support |

## Install (end users)

Download the native installer for your OS from the [latest release](https://github.com/RecordorAI/recordorai-installer/releases/latest) and follow the [install guide](INSTALL.md).

> **v0.1 RC — unsigned builds**
> The first releases ship unsigned while we wait on Apple Developer
> ID and Windows codesigning paperwork. macOS / Windows show a
> one-time "unidentified developer" / SmartScreen warning. The
> [INSTALL.md](INSTALL.md) walks through the bypass — same steps
> every dev-tools project uses during early access. The Tauri
> auto-updater's Ed25519 signature is always on regardless of
> OS-level codesigning, so updates remain tamper-checked.

## Install (developers)

```bash
pip install recordorai-installer
recordorai-install
```

Or run the wizard from a checkout:

```bash
git clone https://github.com/RecordorAI/recordorai-installer
cd recordorai-installer
pip install -e ".[dev]"
recordorai-install
```

The TUI handles every install path the GUI does, plus the
diagnostic flags `--detect`, `--dry-run`, `--rpc`, `--version`.

## Architecture

```
recordorai-installer/
├── src/recordorai_installer/
│   ├── core/              # Headless install logic (no UI)
│   │   ├── detect.py      # OS / Python / GPU / runtimes / palace
│   │   ├── plan.py        # User choices → ordered Step list
│   │   ├── exec_.py       # Execute plan with reverse-order rollback
│   │   ├── license.py     # State machine + 7-day grace period
│   │   └── license_clients/
│   │       ├── lemonsqueezy.py     # Default backend
│   │       ├── keygen.py           # Stripe + Keygen.sh alt
│   │       └── generic.py          # Self-hosted contract
│   ├── adapters/          # One per runtime
│   │   ├── standalone.py
│   │   ├── openclaw.py
│   │   ├── pi_mono.py
│   │   ├── alice_runtime.py
│   │   └── hermes.py
│   ├── tui/               # Textual front-end
│   │   ├── app.py
│   │   ├── state.py
│   │   └── screens/
│   ├── rpc/               # JSON-RPC stdio server (Tauri bridge)
│   │   └── server.py
│   └── cli.py             # `recordorai-install` entry point
│
├── tauri-app/             # Tauri GUI front-end (Sprint 2)
│   ├── src/               # SvelteKit UI
│   └── src-tauri/         # Rust shell + sidecar binary slot
│
├── packaging/             # PyInstaller + sidecar build (Sprint 4)
│   ├── recordorai-install.spec
│   ├── build_sidecar.py
│   └── build_updater_manifest.py
│
├── .github/workflows/
│   └── release.yml        # Tag-push CI matrix → signed installers
│
├── docs/
│   ├── licensing.md       # Operator runbook for LS / Keygen / generic
│   └── packaging.md       # Operator runbook for cert paperwork
│
└── INSTALL.md             # End-user install guide
```

## Status

| Sprint | What | Tests |
|--------|------|------:|
| 1 | Core + TUI + Standalone + OpenClaw adapters | 58 |
| 2 | JSON-RPC + Tauri scaffold + SvelteKit UI | 75 |
| 3 | pi-mono + alice-runtime + Hermes Agent adapters | 89 |
| 5 | LemonSqueezy + Keygen + Generic license backends | 109 |
| 4 | PyInstaller sidecar + Tauri config + GitHub Actions release matrix | 109 |

Engineering is complete. Outstanding items for v0.1 GA are paperwork
(Apple Developer ID, Windows OV cert, Lemon Squeezy product) detailed
in [docs/packaging.md](docs/packaging.md). v0.1 RC unsigned builds
ship while paperwork is in flight.

## Contributing

Follow the existing conventions:

```bash
pip install -e ".[dev]"
pytest tests/ -v          # 109 tests, runs in ~10s
ruff check src/ tests/    # must pass
ruff format src/ tests/
```

Issues + PRs welcome.
