<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { Settings } from '../lib/types';

  let dialog: HTMLDialogElement | undefined = $state();
  let model = $state('');
  let effort = $state<Settings['effort']>('medium');
  let message = $state<MessageKey | null>(null);
  let busy = $state(false);

  const settings = $derived(app.state?.settings);

  $effect(() => {
    if (!dialog) return;
    if (app.settingsOpen && !dialog.open) {
      model = settings?.model ?? '';
      effort = settings?.effort ?? 'medium';
      message = null;
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    const result = await app.act(() => api.put<Settings>('/api/settings', { model, effort }));
    busy = false;
    if (result) message = 'Saved. New lessons, answers and feedback use these settings.';
  }
</script>

<dialog bind:this={dialog} onclose={() => (app.settingsOpen = false)} aria-labelledby="settings-title">
  <header>
    <h2 id="settings-title">{t("Teacher settings")}</h2>
    <button class="btn btn-quiet btn-small" onclick={() => (app.settingsOpen = false)}>{t("Close")}</button>
  </header>
  {#if settings}
    <form onsubmit={save}>
      <p class="intro">{t("Lessons are taught by the Codex CLI on this computer, using your existing Codex sign-in. Text already written stays as it is.")}</p>
      <label class="field">
        <span>{t("Model")}</span>
        <input type="text" bind:value={model} placeholder={t("Leave empty for your Codex default")} autocomplete="off" />
      </label>
      <label class="field">
        <span>{t("Reasoning effort")}</span>
        <select bind:value={effort}>
          <option value="minimal">{t("Minimal")}</option>
          <option value="low">{t("Low")}</option>
          <option value="medium">{t("Medium")}</option>
          <option value="high">{t("High")}</option>
        </select>
      </label>
      <div class="row">
        <button class="btn btn-primary" type="submit" disabled={busy}>{t("Save")}</button>
        {#if message}<span class="message" role="status">{t(message)}</span>{/if}
      </div>
      {#if settings.overridden}
        <p class="note">{t("This host was started with --model or --effort. Saving here replaces them.")}</p>
      {/if}
      <p class="note">{t("Saved for your user account in")} <code>{settings.path}</code>{t(", never inside a course folder.")}</p>
    </form>
  {/if}
</dialog>

<style>
  dialog {
    width: min(30rem, calc(100vw - 2rem));
    padding: 1.25rem 1.5rem 1.5rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.45);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  form {
    display: grid;
    gap: 0.9rem;
  }

  .intro,
  .note {
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .message {
    font-size: var(--step--1);
    color: var(--good);
  }
</style>
