# Icons

Tauri requires icons in 5 formats for the cross-platform bundles:

- `32x32.png`            — Linux desktop entries
- `128x128.png`          — Linux desktop entries
- `128x128@2x.png`       — Linux retina
- `icon.icns`            — macOS bundle
- `icon.ico`             — Windows .msi bundle

Generate these from a single 1024×1024 source PNG with the Tauri CLI:

```bash
bun run tauri icon path/to/source.png
```

This writes all five files into this directory. The placeholder is
intentionally absent — Sprint 4 (packaging) will commit the real
brand asset along with the Apple notarization workflow.
