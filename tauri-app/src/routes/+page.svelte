<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  import { detectEnvironment } from "$lib/rpc";
  import { wizard } from "$lib/wizard";
  import type { Environment } from "$lib/types";

  let env: Environment | null = null;
  let error = "";

  onMount(async () => {
    try {
      env = await detectEnvironment();
      wizard.update((s) => {
        s.env = env;
        if (!s.palaceRoot) {
          s.palaceRoot = env?.palace_root ?? "~/.recordorai";
        }
        if (env && !env.host.is_apple_silicon) {
          s.enableRerankAne = false;
        }
        return s;
      });
    } catch (e) {
      error = String(e);
    }
  });

  function detectedRuntimes(env: Environment) {
    return env.runtimes.filter((r) => r.detected && r.name !== "standalone");
  }
</script>

<h2>Welcome</h2>
<p class="subtitle">
  We'll set up RecordorAI on this machine. Pick the runtime you use,
  enable the ingest types you want, and we'll configure everything for
  you.
</p>

{#if error}
  <div class="card error">
    <strong>Could not start the installer core:</strong>
    <pre>{error}</pre>
    Make sure Python 3.9+ is installed and `recordorai-installer` is
    on PATH.
  </div>
{:else if env}
  <div class="card">
    <dl class="kv">
      <dt>OS</dt>
      <dd>{env.host.os} {env.host.os_version} ({env.host.arch})</dd>

      <dt>Python</dt>
      <dd>{env.python.version.join(".")}</dd>

      <dt>Acceleration</dt>
      <dd>
        {#if env.host.is_apple_silicon}
          Apple Silicon — Neural Engine available
        {:else if env.gpu.has_cuda}
          NVIDIA CUDA {env.gpu.cuda_version ?? ""}
        {:else if env.gpu.has_rocm}
          AMD ROCm
        {:else}
          CPU-only (works for everything; some optional models are slower)
        {/if}
      </dd>

      {#if env.existing_recordorai}
        <dt>Existing</dt>
        <dd>RecordorAI {env.existing_recordorai} (this is an upgrade)</dd>
      {/if}

      {#if env.palace_root}
        <dt>Palace</dt>
        <dd>{env.palace_root}</dd>
      {/if}
    </dl>
  </div>

  <div class="card">
    <strong>Detected runtimes:</strong>
    {#if detectedRuntimes(env).length === 0}
      <p class="muted">
        No host runtimes found — Standalone install path will be the
        default.
      </p>
    {:else}
      <ul>
        {#each detectedRuntimes(env) as r}
          <li>
            {r.name}
            {#if r.version}<span class="muted">— v{r.version}</span>{/if}
          </li>
        {/each}
      </ul>
    {/if}
  </div>
{:else}
  <p class="muted">Detecting environment…</p>
{/if}

<div class="actions">
  <span></span>
  <button class="primary" disabled={!env} on:click={() => goto("/configure")}>
    Continue
  </button>
</div>
