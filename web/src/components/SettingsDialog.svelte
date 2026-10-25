<script lang="ts">
  import { t, locale, type Language, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { CodexModel, Settings } from '../lib/types';

  type Theme = 'system' | 'light' | 'dark';

  let dialog: HTMLDialogElement | undefined = $state();
  let model = $state('');
  let smallModel = $state('');
  let serviceTier = $state('');
  let models = $state<CodexModel[] | null>(null);
  let modelsError = $state('');
  let effort = $state<Settings['effort']>('medium');
  let smallEffort = $state<Settings['small_effort']>('');
  let message = $state<MessageKey | null>(null);
  let busy = $state(false);
  let savingLanguage = $state(false);
  let theme = $state<Theme>((document.documentElement.dataset.theme as Theme | undefined) ?? 'system');

  const settings = $derived(app.settings);
  // The tier Codex calls Fast for the chosen teacher model (or the Codex default model).
  const fastTier = $derived.by(() => {
    const chosen = models?.find((m) => (model ? m.id === model : m.default));
    return chosen?.tiers.find((tier) => tier.name.toLowerCase() === 'fast') ?? null;
  });
  // Without a model list, a saved tier can still be switched off.
  const fastId = $derived(fastTier?.id ?? (models ? '' : serviceTier));

  async function loadModels() {
    if (models) return;
    modelsError = '';
    try {
      models = (await api.get<{ models: CodexModel[] }>('/api/models')).models;
    } catch (error) {
      modelsError = error instanceof Error ? error.message : String(error);
    }
  }

  // A saved model the list does not offer stays selectable rather than being silently replaced.
  function choices(current: string) {
    const list = models ?? [];
    return current && !list.some((m) => m.id === current) ? [...list, { id: current, name: current } as CodexModel] : list;
  }

  $effect(() => {
    if (!dialog) return;
    if (app.settingsOpen && !dialog.open) {
      model = settings?.model ?? '';
      smallModel = settings?.small_model ?? '';
      serviceTier = settings?.service_tier ?? '';
      void loadModels();
      effort = settings?.effort ?? 'medium';
      smallEffort = settings?.small_effort ?? '';
      message = null;
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function changeLanguage(event: Event) {
    const select = event.currentTarget as HTMLSelectElement;
    savingLanguage = true;
    await app.setLanguage(select.value as Language);
    select.value = locale.language;
    savingLanguage = false;
  }

  function changeTheme() {
    const root = document.documentElement;
    if (theme === 'system') delete root.dataset.theme;
    else root.dataset.theme = theme;
    try {
      if (theme === 'system') localStorage.removeItem('theme');
      else localStorage.setItem('theme', theme);
    } catch {
      // The choice still applies for this visit.
    }
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    const result = await app.act(() => api.put<Settings>('/api/settings', {
      model,
      small_model: smallModel,
      effort,
      small_effort: smallEffort,
      // A teacher model without a Fast tier runs at the standard speed.
      service_tier: models && !fastTier ? '' : serviceTier,
    }));
    busy = false;
    if (result) {
      app.settings = result;
      message = 'Saved. New lessons, answers and feedback use these settings.';
    }
  }
</script>

<dialog bind:this={dialog} onclose={() => (app.settingsOpen = false)} aria-labelledby="settings-title">
  <header>
    <h2 id="settings-title">{t("Settings")}</h2>
    <button class="btn btn-quiet btn-small" onclick={() => (app.settingsOpen = false)}>{t("Close")}</button>
  </header>

  <section aria-labelledby="language-title">
    <h3 id="language-title">{t("Language")}</h3>
    <label class="field">
      <span class="visually-hidden">{t("Language")}</span>
      <select aria-label={t("Language")} value={locale.language} onchange={changeLanguage} disabled={savingLanguage}>
        <option value="en">English</option>
        <option value="zh-CN">简体中文</option>
      </select>
    </label>
    <p class="note">
      {app.state
        ? t("For this course: the interface and new teaching content. Sources and saved lessons keep their language.")
        : t("For this page. Each course keeps its own language once it is open.")}
    </p>
  </section>

  <section aria-labelledby="theme-title">
    <h3 id="theme-title">{t("Appearance")}</h3>
    <label class="field">
      <span class="visually-hidden">{t("Appearance")}</span>
      <select aria-label={t("Appearance")} bind:value={theme} onchange={changeTheme}>
        <option value="system">{t("Match the system")}</option>
        <option value="light">{t("Light")}</option>
        <option value="dark">{t("Dark")}</option>
      </select>
    </label>
  </section>

  <section aria-labelledby="teacher-title">
    <h3 id="teacher-title">{t("Teacher")}</h3>
    {#if settings}
      <form onsubmit={save}>
        <p class="note">{t("Lessons are taught by the Codex CLI on this computer, using your existing Codex sign-in. Text already written stays as it is.")}</p>
        {#if models}
          <label class="field">
            <span>{t("Model")}</span>
            <select bind:value={model}>
              <option value="">{t("Codex default")}</option>
              {#each choices(model) as option (option.id)}
                <option value={option.id} title={option.description}>{option.name}</option>
              {/each}
            </select>
          </label>
          <label class="field">
            <span>{t("Small model")}</span>
            <select bind:value={smallModel}>
              <option value="">{t("Same as the teacher model")}</option>
              {#each choices(smallModel) as option (option.id)}
                <option value={option.id} title={option.description}>{option.name}</option>
              {/each}
            </select>
          </label>
        {:else}
          <label class="field">
            <span>{t("Model")}</span>
            <input type="text" bind:value={model} placeholder={t("Leave empty for your Codex default")} autocomplete="off" />
          </label>
          <label class="field">
            <span>{t("Small model")}</span>
            <input type="text" bind:value={smallModel} placeholder={t("Leave empty to use the teacher model")} autocomplete="off" />
          </label>
          {#if modelsError}
            <p class="note">{t("Could not load models from Codex:")} {modelsError}</p>
          {:else}
            <p class="note" role="status">{t("Loading models from Codex…")}</p>
          {/if}
        {/if}
        <p class="note">{t("The small model prepares upcoming sections and consolidates notes in the background.")}</p>
        <label class="field">
          <span>{t("Reasoning effort")}</span>
          <select bind:value={effort}>
            <option value="minimal">{t("Minimal")}</option>
            <option value="low">{t("Low")}</option>
            <option value="medium">{t("Medium")}</option>
            <option value="high">{t("High")}</option>
          </select>
        </label>
        <label class="field">
          <span>{t("Small model reasoning effort")}</span>
          <select bind:value={smallEffort}>
            <option value="">{t("Same as the teacher")}</option>
            <option value="minimal">{t("Minimal")}</option>
            <option value="low">{t("Low")}</option>
            <option value="medium">{t("Medium")}</option>
            <option value="high">{t("High")}</option>
          </select>
        </label>
        {#if fastId}
          <label class="check">
            <input
              type="checkbox"
              checked={serviceTier === fastId}
              onchange={(event) => (serviceTier = event.currentTarget.checked ? fastId : '')}
            />
            <span>{t("Fast mode")}</span>
          </label>
          <p class="note">
            {fastTier?.description ? `${fastTier.description}. ` : ''}{t("Applies to lessons, answers and feedback; background preparation keeps the standard speed.")}
          </p>
        {/if}
        <div class="row">
          <button class="btn btn-primary" type="submit" disabled={busy}>{t("Save")}</button>
          {#if message}<span class="message" role="status">{t(message)}</span>{/if}
        </div>
        {#if settings.overridden}
          <p class="note">{t("This host was started with model or effort options. Saving here replaces them.")}</p>
        {/if}
        <p class="note">{t("Saved for your user account in")} <code>{settings.path}</code>{t(", never inside a course folder.")}</p>
      </form>
    {/if}
  </section>
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

  section {
    display: grid;
    gap: 0.5rem;
    padding-block: 1rem;
    border-top: 1px solid var(--rule);
  }

  h3 {
    font-family: var(--sans);
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

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

  .check {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .message {
    font-size: var(--step--1);
    color: var(--good);
  }
</style>
