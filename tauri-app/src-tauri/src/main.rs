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

fn main() {
    let client = match RpcClient::spawn_python() {
        Ok(c) => c,
        Err(e) => {
            eprintln!(
                "FATAL: Could not spawn the RecordorAI installer core: {}\n\
                 Make sure Python 3.9+ is installed and `recordorai-installer` is reachable.",
                e
            );
            std::process::exit(2);
        }
    };
    let shared: SharedClient = Arc::new(Mutex::new(client));

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(shared)
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
