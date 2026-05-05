/**
 * Tauri-side RPC client. Each function wraps a Tauri command exposed
 * by `src-tauri/src/main.rs`; the Rust shell forwards the call to the
 * Python subprocess via JSON-RPC over stdio.
 *
 * Streaming `installer.execute` notifications arrive as Tauri events
 * on the `install:event` channel — see `subscribeInstallEvents`.
 */

import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import type {
  Choices,
  Environment,
  ExecResultSummary,
  InstallEvent,
  LicenseStatus,
  Plan,
} from "./types";

export async function ping(): Promise<string> {
  return invoke<string>("rpc_ping");
}

export async function detectEnvironment(): Promise<Environment> {
  return invoke<Environment>("installer_detect");
}

export async function supportedRuntimes(): Promise<string[]> {
  return invoke<string[]>("installer_supported_runtimes");
}

export async function buildPlan(choices: Choices): Promise<Plan> {
  // Filter undefined keys so the Python-side `Choices(**kwargs)`
  // doesn't error on unexpected None values.
  const cleaned: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(choices)) {
    if (v !== undefined && v !== null) cleaned[k] = v;
  }
  return invoke<Plan>("installer_build_plan", { choices: cleaned });
}

export async function validateLicense(
  licenseKey: string,
  online = true,
): Promise<LicenseStatus> {
  return invoke<LicenseStatus>("installer_validate_license", {
    licenseKey,
    online,
  });
}

export async function executeInstall(
  choices: Choices,
): Promise<ExecResultSummary> {
  const cleaned: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(choices)) {
    if (v !== undefined && v !== null) cleaned[k] = v;
  }
  return invoke<ExecResultSummary>("installer_execute", { choices: cleaned });
}

/**
 * Subscribe to install.event notifications during a running install.
 * Returns an unlisten function — call it when the install finishes.
 *
 *     const off = await subscribeInstallEvents((ev) => log(ev));
 *     await executeInstall(choices);
 *     off();
 */
export async function subscribeInstallEvents(
  handler: (event: InstallEvent) => void,
): Promise<UnlistenFn> {
  return listen<InstallEvent>("install:event", (e) => handler(e.payload));
}
