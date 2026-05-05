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

## Install (developers)

```
pip install recordorai-installer
recordorai-install
```

## Install (end users)

Download the native installer for your OS from <https://recordorai.com/download> and double-click.

## Status

Sprint 1 in progress. Standalone + OpenClaw adapters first; pi-mono / Alice-runtime / Hermes Agent in Sprint 3.
