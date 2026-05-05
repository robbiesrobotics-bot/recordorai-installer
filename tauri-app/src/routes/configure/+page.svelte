<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  import {
    supportedRuntimes,
    validateLicense as rpcValidate,
  } from "$lib/rpc";
  import { wizard, proUnlocked } from "$lib/wizard";

  let runtimes: string[] = [];
  let validating = false;
  let licenseFeedback = "";

  onMount(async () => {
    try {
      runtimes = await supportedRuntimes();
    } catch (e) {
      runtimes = ["standalone"];
    }
  });

  async function validateLicense() {
    validating = true;
    licenseFeedback = "Validating…";
    try {
      const status = await rpcValidate($wizard.licenseKey);
      wizard.update((s) => {
        s.licenseStatus = status;
        return s;
      });
      licenseFeedback = `${status.state}: ${status.message}`;
    } catch (e) {
      licenseFeedback = `Error: ${e}`;
    } finally {
      validating = false;
    }
  }

  function isEligible(name: string): boolean {
    if (!$wizard.env) return name === "standalone";
    if (name === "standalone") return true;
    return $wizard.env.runtimes.some((r) => r.name === name && r.detected);
  }

  $: pro = proUnlocked($wizard);
</script>

<h2>Configure</h2>
<p class="subtitle">
  Pick your edition, your agent runtime, and the ingest types you want.
</p>

<!-- Edition -->
<div class="card">
  <strong>Edition</strong>
  <div class="runtime-list" style="margin-top: 12px">
    <label class="runtime-row">
      <input
        type="radio"
        bind:group={$wizard.edition}
        value="community"
      />
      <div>
        <strong>Community</strong> — free
        <div class="muted">
          All retrieval. All ingest types. All five runtime integrations.
          Single-user, single-machine.
        </div>
      </div>
    </label>

    <label class="runtime-row">
      <input type="radio" bind:group={$wizard.edition} value="pro" />
      <div>
        <strong>Pro</strong> — monthly subscription
        <div class="muted">
          Multi-tenant (per-user palaces), cross-device sync, Smart
          Observer, priority support.
        </div>
      </div>
    </label>
  </div>

  {#if $wizard.edition === "pro"}
    <div style="margin-top: 16px">
      <label>License key:</label>
      <input
        type="text"
        placeholder="RAI-PRO-XXXX-XXXX-XXXX"
        bind:value={$wizard.licenseKey}
      />
      <div class="actions">
        <span></span>
        <button on:click={validateLicense} disabled={validating || !$wizard.licenseKey}>
          {validating ? "Validating…" : "Validate"}
        </button>
      </div>
      {#if licenseFeedback}
        <p
          class={pro ? "ok" : licenseFeedback.startsWith("Error") ? "error" : "muted"}
        >
          {licenseFeedback}
        </p>
      {/if}
    </div>
  {/if}
</div>

<!-- Runtime -->
<div class="card">
  <strong>Runtime</strong>
  <div class="runtime-list" style="margin-top: 12px">
    {#each runtimes as r}
      {@const eligible = isEligible(r)}
      <label class={eligible ? "runtime-row" : "runtime-row disabled"}>
        <input
          type="radio"
          bind:group={$wizard.runtime}
          value={r}
          disabled={!eligible}
        />
        <div>
          <strong>{r}</strong>
          {#if !eligible}<span class="muted"> — not detected</span>{/if}
        </div>
      </label>
    {/each}
  </div>
</div>

<!-- Features -->
<div class="card">
  <strong>Features</strong>

  <div style="margin-top: 12px">
    <label>Palace root:</label>
    <input type="text" bind:value={$wizard.palaceRoot} placeholder="~/.recordorai" />
  </div>

  <div class="feature-list" style="margin-top: 16px">
    <label class="feature-row">
      <input type="checkbox" bind:checked={$wizard.enableDocuments} />
      <div>
        <strong>Documents</strong> — PDF, .docx, .pptx, HTML
        <div class="muted">Small, recommended.</div>
      </div>
    </label>

    <label class="feature-row">
      <input type="checkbox" bind:checked={$wizard.enableAudio} />
      <div>
        <strong>Audio</strong> — voice memos via WhisperX
        <div class="muted">~3 GB model, downloads on first run.</div>
      </div>
    </label>

    <label class="feature-row">
      <input type="checkbox" bind:checked={$wizard.enableImage} />
      <div>
        <strong>Image</strong> — screenshots/photos via Qwen3-VL
        <div class="muted">~3 GB model.</div>
      </div>
    </label>

    <label class="feature-row">
      <input type="checkbox" bind:checked={$wizard.enableVideo} />
      <div>
        <strong>Video</strong> — mp4/mov via ffmpeg + audio + image
        <div class="muted">Requires ffmpeg on PATH.</div>
      </div>
    </label>

    {#if $wizard.env?.host.is_apple_silicon}
      <label class="feature-row">
        <input type="checkbox" bind:checked={$wizard.enableRerankAne} />
        <div>
          <strong>ANE-accelerated rerank</strong>
          <div class="muted">Recommended for M-series Macs.</div>
        </div>
      </label>
    {/if}
  </div>

  {#if $wizard.edition === "pro" && pro}
    <div style="margin-top: 16px">
      <strong>Pro features</strong>
      <div class="feature-list" style="margin-top: 12px">
        <label class="feature-row">
          <input type="checkbox" bind:checked={$wizard.enableMultiTenant} />
          <div>Multi-tenant (per-user palaces with ACLs)</div>
        </label>
        <label class="feature-row">
          <input type="checkbox" bind:checked={$wizard.enableSync} />
          <div>Cross-device sync (encrypted)</div>
        </label>
        <label class="feature-row">
          <input type="checkbox" bind:checked={$wizard.enableSmartObserver} />
          <div>Smart Observer (LLM-augmented capsule generation)</div>
        </label>
      </div>
    </div>
  {/if}
</div>

<div class="actions">
  <button on:click={() => goto("/")}>Back</button>
  <button class="primary" on:click={() => goto("/install")}>
    Continue to Install
  </button>
</div>
