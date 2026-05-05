// RecordorAI Installer — Tauri shell entry point.
//
// Spawns `python -m recordorai_installer --rpc` once at startup and
// keeps the handle in shared state. Each Tauri command issues one
// JSON-RPC request and returns the response; install.event
// notifications are forwarded as Tauri events to the SvelteKit UI.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod rpc;

use std::sync::Arc;

use rpc::RpcClient;
use serde_json::Value;
use tauri::Manager;
use tokio::sync::Mutex;

// Shared state — single RpcClient instance, locked across commands.
type SharedClient = Arc<Mutex<RpcClient>>;

#[tauri::command]
async fn rpc_ping(client: tauri::State<'_, SharedClient>) -> Result<Value, String> {
    let mut c = client.lock().await;
    c.call("rpc.ping", Value::Null).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn installer_detect(
    client: tauri::State<'_, SharedClient>,
) -> Result<Value, String> {
    let mut c = client.lock().await;
    c.call("installer.detect", Value::Null).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn installer_supported_runtimes(
    client: tauri::State<'_, SharedClient>,
) -> Result<Value, String> {
    let mut c = client.lock().await;
    c.call("installer.supported_runtimes", Value::Null)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn installer_build_plan(
    client: tauri::State<'_, SharedClient>,
    choices: Value,
) -> Result<Value, String> {
    let mut c = client.lock().await;
    c.call("installer.build_plan", choices)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn installer_validate_license(
    client: tauri::State<'_, SharedClient>,
    license_key: String,
    online: Option<bool>,
) -> Result<Value, String> {
    let mut c = client.lock().await;
    let mut params = serde_json::Map::new();
    params.insert("license_key".into(), Value::String(license_key));
    if let Some(o) = online {
        params.insert("online".into(), Value::Bool(o));
    }
    c.call("installer.validate_license", Value::Object(params))
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn installer_execute(
    app: tauri::AppHandle,
    client: tauri::State<'_, SharedClient>,
    choices: Value,
) -> Result<Value, String> {
    // installer.execute streams install.event notifications. Forward
    // them as Tauri events on the "install:event" channel so the
    // SvelteKit UI's progress widget can subscribe via @tauri-apps/api.
    let app_handle = app.clone();
    let mut c = client.lock().await;
    c.call_streaming("installer.execute", choices, move |notification| {
        // notification looks like:
        //   {"jsonrpc":"2.0","method":"install.event","params":{...}}
        if let Some(params) = notification.get("params") {
            let _ = app_handle.emit("install:event", params.clone());
        }
    })
    .await
    .map_err(|e| e.to_string())
}

/// Resolve the path to the PyInstaller-frozen sidecar that ships
/// alongside the Tauri app.
///
/// Tauri 2's `externalBin` mechanism places the sidecar binary
/// inside the app's resource dir at bundle time, with the platform's
/// canonical name (no `-<triple>` suffix once installed; the suffix
/// is only used during the bundler's build step).
///
/// macOS:   <App>.app/Contents/Resources/recordorai-install
/// Windows: <Install dir>/resources/recordorai-install.exe
/// Linux:   <Install dir>/resources/recordorai-install   (or
///          /usr/lib/recordorai-installer/recordorai-install for .deb)
///
/// We use Tauri's PathResolver which abstracts these per-OS layouts.
fn resolve_sidecar_path(app: &tauri::AppHandle) -> Option<std::path::PathBuf> {
    use tauri::Manager;

    let exe = if cfg!(target_os = "windows") {
        "recordorai-install.exe"
    } else {
        "recordorai-install"
    };

    // Tauri 2 stores externalBin under <resources>/<name>.
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidate = resource_dir.join(exe);
        if candidate.exists() {
            return Some(candidate);
        }
    }

    // Fallback: look next to the running executable. Some Tauri
    // bundle layouts (notably AppImage on Linux) place the sidecar
    // there instead of resource_dir.
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            let candidate = parent.join(exe);
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }

    None
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Production path: spawn the PyInstaller sidecar so the
            // user's machine doesn't need a Python install.
            // Dev fallback: if no sidecar (running cargo run / bun
            // tauri dev), shell out to system Python.
            let client = match resolve_sidecar_path(&app.handle()) {
                Some(path) => RpcClient::spawn_sidecar(&path),
                None => {
                    eprintln!(
                        "[RecordorAI] No sidecar found — falling back to \
                         system Python (dev mode). Run `python \
                         packaging/build_sidecar.py` to bundle the \
                         frozen Python."
                    );
                    RpcClient::spawn_python()
                }
            };

            let client = match client {
                Ok(c) => c,
                Err(e) => {
                    eprintln!(
                        "FATAL: Could not start the RecordorAI installer \
                         core: {}",
                        e
                    );
                    std::process::exit(2);
                }
            };

            app.manage::<SharedClient>(Arc::new(Mutex::new(client)));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            rpc_ping,
            installer_detect,
            installer_supported_runtimes,
            installer_build_plan,
            installer_validate_license,
            installer_execute,
        ])
        .run(tauri::generate_context!())
        .expect("Tauri app failed to start");
}
