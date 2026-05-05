import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

// Vite config tuned for Tauri:
//   - Fixed port 1420 (matches tauri.conf.json devUrl)
//   - No fallback to a different port if 1420 is busy
//   - Tauri envvars are available via `import.meta.env.TAURI_*`
export default defineConfig({
  plugins: [sveltekit()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    // Watching node_modules/* keeps tauri's HMR snappy
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
});
