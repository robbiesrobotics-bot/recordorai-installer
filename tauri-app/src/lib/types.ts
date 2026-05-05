/**
 * TypeScript mirrors of the Python dataclasses in
 * `recordorai_installer.core`. Keeping them in lockstep lets the
 * Svelte UI consume RPC results directly without runtime decoding.
 *
 * If a Python dataclass changes, update this file in the same PR
 * (Sprint 2's CI will check for missing fields once it's wired).
 */

export interface HostInfo {
  os: "macos" | "windows" | "linux" | string;
  arch: "arm64" | "x86_64" | "x86" | string;
  os_version: string;
  is_apple_silicon: boolean;
}

export interface PythonInfo {
  executable: string;
  version: [number, number, number];
  is_venv: boolean;
  site_packages: string;
}

export interface GPUInfo {
  has_apple_neural_engine: boolean;
  has_cuda: boolean;
  has_rocm: boolean;
  cuda_version: string | null;
}

export interface RuntimeInfo {
  name: "standalone" | "openclaw" | "pi-mono" | "alice-runtime" | "hermes" | string;
  detected: boolean;
  install_path: string | null;
  version: string | null;
  config_path: string | null;
  notes: string;
}

export interface Environment {
  host: HostInfo;
  python: PythonInfo;
  gpu: GPUInfo;
  runtimes: RuntimeInfo[];
  existing_recordorai: string | null;
  palace_root: string | null;
}

export interface Choices {
  runtime: string;
  palace_root: string;
  edition: "community" | "pro";
  license_key?: string | null;
  enable_audio?: boolean;
  enable_image?: boolean;
  enable_video?: boolean;
  enable_documents?: boolean;
  enable_rerank_ane?: boolean;
  enable_multi_tenant?: boolean;
  enable_sync?: boolean;
  enable_smart_observer?: boolean;
}

export interface PlanStep {
  kind: "deps" | "fs" | "config" | "register" | "verify" | "license" | string;
  title: string;
  detail: string;
  metadata: Record<string, unknown>;
}

export interface Plan {
  summary: string;
  kinds: string[];
  steps: PlanStep[];
}

export type LicenseStateName =
  | "new"
  | "active"
  | "grace"
  | "grace_expired"
  | "expired"
  | "invalid";

export interface LicenseStatus {
  state: LicenseStateName;
  edition: "community" | "pro";
  plan: string;
  last_validated_iso: string | null;
  expires_iso: string | null;
  grace_days_remaining: number | null;
  customer_email: string | null;
  message: string;
}

/** install.event notification payload sent during installer.execute. */
export interface InstallEvent {
  type:
    | "plan_start"
    | "step_start"
    | "step_ok"
    | "step_warn"
    | "step_fail"
    | "rollback_start"
    | "rollback_step"
    | "rollback_done"
    | "plan_ok"
    | "plan_fail";
  step_title: string | null;
  step_kind: string | null;
  index: number;
  total: number;
  message: string;
  elapsed_s: number;
  error: string | null;
}

export interface ExecResultSummary {
  success: boolean;
  elapsed_s: number;
  completed_count: number;
  failed_step_title: string | null;
  error: string | null;
}
