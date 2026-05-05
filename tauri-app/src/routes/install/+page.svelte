<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  import {
    buildPlan,
    executeInstall,
    subscribeInstallEvents,
  } from "$lib/rpc";
  import { wizard, toChoices } from "$lib/wizard";
  import type { ExecResultSummary, InstallEvent, Plan } from "$lib/types";

  let plan: Plan | null = null;
  let log: string[] = [];
  let running = false;
  let result: ExecResultSummary | null = null;
  let error = "";

  onMount(async () => {
    try {
      plan = await buildPlan(toChoices($wizard));
    } catch (e) {
      error = String(e);
    }
  });

  async function install() {
    if (!plan) return;
    running = true;
    log = [];
    result = null;
    error = "";

    let unsubscribe = await subscribeInstallEvents((ev) => {
      log = [...log, formatEvent(ev)];
    });

    try {
      result = await executeInstall(toChoices($wizard));
    } catch (e) {
      error = String(e);
    } finally {
      unsubscribe();
      running = false;
    }
  }

  function formatEvent(ev: InstallEvent): string {
    switch (ev.type) {
      case "plan_start":
        return `Starting ${ev.total} step(s)…`;
      case "step_start":
        return `[${ev.index + 1}/${ev.total}] ${ev.step_title}`;
      case "step_ok":
        return `      ✓ (${ev.elapsed_s.toFixed(2)}s)`;
      case "step_warn":
        return `      ⚠ ${ev.message}`;
      case "step_fail":
        return `      ✗ ${ev.message}`;
      case "rollback_start":
        return `\nRolling back ${ev.total} step(s)…`;
      case "rollback_step":
        return `  rollback: ${ev.step_title} ${ev.error ? `(undo failed: ${ev.error})` : ""}`;
      case "plan_ok":
        return `\nDone in ${ev.elapsed_s.toFixed(1)}s.`;
      case "plan_fail":
        return `\nFAILED in ${ev.elapsed_s.toFixed(1)}s.`;
      default:
        return "";
    }
  }
</script>

<h2>Install</h2>
<p class="subtitle">
  Review the plan, then press Install. Anything that fails will be
  rolled back automatically.
</p>

{#if error}
  <div class="card error">
    <strong>Error:</strong>
    <pre>{error}</pre>
  </div>
{:else if plan}
  <div class="card">
    <strong>{plan.summary}</strong>
  </div>

  <div class="card">
    <strong>Steps:</strong>
    <pre class="steps-list">{plan.steps
      .map((s, i) => `${String(i + 1).padStart(2, " ")}. [${s.kind.padEnd(8, " ")}] ${s.title}`)
      .join("\n")}</pre>
  </div>

  {#if log.length || running}
    <div class="card">
      <strong>Progress:</strong>
      <div class="progress">{log.join("\n")}</div>
    </div>
  {/if}

  {#if result}
    <div class="card">
      {#if result.success}
        <p class="ok">
          ✓ RecordorAI installed successfully in {result.elapsed_s.toFixed(1)}s
          ({result.completed_count} step(s)).
        </p>
        <p>You can now close this window or run <code>recordorai --version</code> to verify.</p>
      {:else}
        <p class="error">
          ✗ Install failed at step {result.failed_step_title}: {result.error}.
          The plan was rolled back; your machine is in its original state.
        </p>
      {/if}
    </div>
  {/if}

  <div class="actions">
    <button disabled={running} on:click={() => goto("/configure")}>Back</button>
    <button
      class="primary"
      disabled={running || result?.success}
      on:click={install}
    >
      {running ? "Installing…" : result ? (result.success ? "Done" : "Retry") : "Install"}
    </button>
  </div>
{:else}
  <p class="muted">Building install plan…</p>
{/if}
