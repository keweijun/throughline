<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';

  /**
   * On a Windows computer without Codex's sandbox, Library access cannot run (ADR 0016): the learner sets the sandbox
   * up, as Codex's own app offers, or chooses Full access knowingly. Studio never switches to Full access by itself.
   */
  let busy = $state(false);
  const access = $derived(studio.access);

  async function run(action: () => Promise<unknown>) {
    busy = true;
    try {
      await action();
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    busy = false;
  }
</script>

{#if access?.sandbox_missing && !access.full_access}
  <section class="sandbox" aria-label={t("Codex's sandbox")}>
    <h3>{t("Codex's sandbox is not set up on this Windows computer")}</h3>
    <p>{t("With Library access, Codex writes only inside your Throughline folder, and it needs its sandbox for that. Set it up once, or let Codex work without it.")}</p>
    {#if access.setting_up}
      <p role="status">{t("Setting up the sandbox… Windows may ask whether Codex can make changes.")}</p>
    {:else if access.setup_error}
      <p class="failed" role="status">{t("The sandbox was not set up: {error}", { error: access.setup_error })}</p>
    {/if}
    <div class="actions">
      <button class="btn btn-small btn-primary" disabled={busy || access.setting_up} onclick={() => run(() => studio.setUpSandbox())}>
        {access.setup_error ? t("Try again") : t("Set up the sandbox")}
      </button>
      <button class="btn btn-small btn-quiet" disabled={busy} onclick={() => run(() => studio.setFullAccess(true))}>{t("Use Full access")}</button>
    </div>
    <p class="meta">{t("Full access: Codex can change files anywhere and runs commands without asking. You can change this in the access menu below.")}</p>
  </section>
{/if}

<style>
  .sandbox {
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    gap: 0.5rem;
    padding: 0.7rem 0.8rem;
    border: 1px solid var(--caution);
    border-radius: calc(var(--radius) * 2);
    background: var(--caution-wash);
    font-size: var(--step--1);
  }

  h3 {
    font-size: var(--step--1);
    font-weight: 600;
  }

  p {
    margin: 0;
    color: var(--ink-soft);
  }

  .meta {
    color: var(--pencil);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
</style>
