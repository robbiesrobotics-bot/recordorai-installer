/**
 * Wizard state — Svelte writable store mirroring the Python
 * `WizardState` class. Each route reads + mutates it; the final
 * `/install` route freezes it into a `Choices` object and hands to
 * `executeInstall`.
 */

import { writable } from "svelte/store";

import type { Choices, Environment, LicenseStatus } from "./types";

export interface WizardState {
  env: Environment | null;

  // Edition step.
  edition: "community" | "pro";
  licenseKey: string;
  licenseStatus: LicenseStatus | null;

  // Runtime step.
  runtime: string;

  // Features step.
  palaceRoot: string;
  enableAudio: boolean;
  enableImage: boolean;
  enableVideo: boolean;
  enableDocuments: boolean;
  enableRerankAne: boolean;
  enableMultiTenant: boolean;
  enableSync: boolean;
  enableSmartObserver: boolean;
}

const initial: WizardState = {
  env: null,
  edition: "community",
  licenseKey: "",
  licenseStatus: null,
  runtime: "standalone",
  palaceRoot: "",
  enableAudio: false,
  enableImage: false,
  enableVideo: false,
  enableDocuments: true,
  enableRerankAne: true,
  enableMultiTenant: false,
  enableSync: false,
  enableSmartObserver: false,
};

export const wizard = writable<WizardState>(initial);

/** Snapshot the current wizard state into the immutable Choices
 * shape consumed by `installer_build_plan` / `installer_execute`.
 */
export function toChoices(state: WizardState): Choices {
  return {
    runtime: state.runtime,
    palace_root: state.palaceRoot,
    edition: state.edition,
    license_key: state.licenseKey || null,
    enable_audio: state.enableAudio,
    enable_image: state.enableImage,
    enable_video: state.enableVideo,
    enable_documents: state.enableDocuments,
    enable_rerank_ane: state.enableRerankAne,
    enable_multi_tenant: state.enableMultiTenant,
    enable_sync: state.enableSync,
    enable_smart_observer: state.enableSmartObserver,
  };
}

/** Returns true iff the license unlocks Pro features. */
export function proUnlocked(state: WizardState): boolean {
  if (!state.licenseStatus) return false;
  return (
    state.licenseStatus.state === "active" ||
    state.licenseStatus.state === "grace"
  );
}
