# RecordorAI Installer — Tauri front-end

Native installer GUI for end users. Wraps the Python core
(`recordorai_installer`) via JSON-RPC over stdio.

## Architecture

```
┌──────────────────────┐     stdio JSON-RPC 2.0     ┌─────────────────────────┐
│  Tauri shell (Rust)  │ ──────────────────────────► │  python -m              │
│  + SvelteKit UI      │ ◄────────────────────────── │  recordorai_installer   │
│                      │   notifications +           │   --rpc                 │
│  - 3-step wizard     │   responses                 │  (subprocess)           │
└──────────────────────┘                             └─────────────────────────┘
```

The Rust shell launches `python -m recordorai_installer --rpc` as a
subprocess, pipes stdin/stdout, and forwards JSON-RPC traffic to the
SvelteKit UI via Tauri's `invoke` IPC and `event` channel.

## Build

Prerequisites:

- Rust toolchain (`rustup`)
- Node 20+ and Bun (or pnpm)
- Tauri CLI: `cargo install tauri-cli` or `bun add -d @tauri-apps/cli`
- Python 3.9+ with `recordorai-installer` installed (so the bundled
  binary can find `python -m recordorai_installer`)

```bash
# Install JS deps
bun install

# Dev mode — hot-reload the UI, Rust shell debug build
bun run tauri dev

# Production build — native installer per OS
bun run tauri build
```

Outputs land in `src-tauri/target/release/bundle/`:

- `dmg/RecordorAI-Installer_<version>_aarch64.dmg` (macOS arm64)
- `msi/RecordorAI-Installer_<version>_x64.msi` (Windows)
- `appimage/RecordorAI-Installer_<version>_amd64.AppImage` (Linux)
- `deb/`, `rpm/` (Linux package managers)

## Sprint 2 status

The scaffold ships with:

- Rust shell that spawns the Python RPC subprocess and exposes 4
  Tauri commands (`detect`, `build_plan`, `validate_license`,
  `execute`).
- SvelteKit UI with 3 routes (`/`, `/configure`, `/install`).
- TypeScript types mirroring the Python dataclasses
  (`src/lib/types.ts`).

The actual `tauri build` requires the user's machine to have the Rust
+ Node toolchains installed; this repo only ships the source. Sprint
4 wires CI to do the cross-platform builds + signing on tag push.
