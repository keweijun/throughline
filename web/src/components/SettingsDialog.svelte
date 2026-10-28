<script lang="ts">
  import { t, locale, type Language, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { CodexModel, Settings, UpdateCheck } from '../lib/types';
  import CodexLink from './CodexLink.svelte';

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
  let dailyReviews = $state(5);
  let savingReviews = $state(false);
  type Tab = 'general' | 'about';
  const TABS: { id: Tab; label: MessageKey }[] = [
    { id: 'general', label: 'General' },
    { id: 'about', label: 'About' },
  ];
  let tab = $state<Tab>('general');
  let about = $state<{ version: string } | null>(null);
  let update = $state<UpdateCheck | null>(null);
  let updateError = $state('');
  let checking = $state(false);
  let theme = $state<Theme>((document.documentElement.dataset.theme as Theme | undefined) ?? 'system');

  const settings = $derived(app.settings);
  const confirmedPreferences = $derived(
    app.state?.memory.filter((entry) => entry.kind === 'preference' && entry.status === 'confirmed').length ?? 0,
  );
  // The tier Codex calls Fast for the chosen teacher model (or the Codex default model).
  const fastTier = $derived.by(() => {
    const chosen = models?.find((m) => (model ? m.id === model : m.default));
    return chosen?.tiers.find((tier) => tier.name.toLowerCase() === 'fast') ?? null;
  });
  // Without a model list, a saved tier can still be switched off.
  const fastId = $derived(fastTier?.id ?? (models ? '' : serviceTier));

  // Offer only the reasoning efforts the chosen model supports; the saved one stays selectable either way.
  const EFFORTS: { id: Settings['effort']; label: MessageKey }[] = [
    { id: 'minimal', label: 'Minimal' },
    { id: 'low', label: 'Low' },
    { id: 'medium', label: 'Medium' },
    { id: 'high', label: 'High' },
  ];
  function effortsFor(id: string) {
    const chosen = models?.find((m) => (id ? m.id === id : m.default));
    const offered = EFFORTS.filter((e) => chosen?.efforts?.includes(e.id));
    return offered.length ? offered : EFFORTS;
  }
  const teacherEfforts = $derived(effortsFor(model));
  const smallEfforts = $derived(effortsFor(smallModel || model));
  // Switching to a model without the chosen effort picks the nearest one it has, at or below the old choice if possible.
  function nearest(current: Settings['effort'], offered: typeof EFFORTS) {
    if (offered.some((e) => e.id === current)) return current;
    const rank = EFFORTS.findIndex((e) => e.id === current);
    return ([...offered].reverse().find((e) => EFFORTS.indexOf(e) < rank) ?? offered[0]).id;
  }
  $effect(() => {
    effort = nearest(effort, teacherEfforts);
  });
  $effect(() => {
    if (smallEffort) smallEffort = nearest(smallEffort, smallEfforts);
  });


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
      dailyReviews = app.state?.preferences.daily_reviews ?? 5;
      message = null;
      tab = 'general';
      void loadAbout();
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

  async function changeDailyReviews() {
    const saved = app.state?.preferences.daily_reviews ?? 5;
    if (!Number.isInteger(dailyReviews) || dailyReviews < 1 || dailyReviews > 20) {
      dailyReviews = saved;
      return;
    }
    if (dailyReviews === saved) return;
    savingReviews = true;
    dailyReviews = (await app.savePreferences({ daily_reviews: dailyReviews }))?.daily_reviews ?? saved;
    savingReviews = false;
  }

  // Tabs follow the ARIA tabs pattern: arrow keys move between them.
  function moveTab(event: KeyboardEvent) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const next = TABS[(TABS.findIndex((o) => o.id === tab) + (event.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length];
    tab = next.id;
    document.getElementById(`settings-tab-${next.id}`)?.focus();
  }

  async function loadAbout() {
    if (about) return;
    try {
      about = await api.get<{ version: string }>('/api/about');
    } catch {
      // The tab still works without the version.
    }
  }

  async function checkForUpdates() {
    checking = true;
    updateError = '';
    try {
      update = await api.get<UpdateCheck>('/api/update');
    } catch (error) {
      update = null;
      updateError = error instanceof Error ? error.message : String(error);
    }
    checking = false;
  }

  function openMemory() {
    app.settingsOpen = false;
    app.openPanel('memory');
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

  <div class="tabs" role="tablist" aria-label={t("Settings")}>
    {#each TABS as option (option.id)}
      <button
        type="button"
        role="tab"
        id="settings-tab-{option.id}"
        aria-controls="settings-panel-{option.id}"
        aria-selected={tab === option.id}
        tabindex={tab === option.id ? 0 : -1}
        onclick={() => (tab = option.id)}
        onkeydown={moveTab}
      >{t(option.label)}</button>
    {/each}
  </div>

  <div id="settings-panel-general" role="tabpanel" aria-labelledby="settings-tab-general" hidden={tab !== 'general'}>
    <section aria-labelledby="course-title">
      <h3 id="course-title">{t(app.state ? "Course" : "Language")}</h3>
      <label class="field">
        <span class:visually-hidden={!app.state}>{t("Language")}</span>
        <select value={locale.language} onchange={changeLanguage} disabled={savingLanguage}>
          <option value="en">English</option>
          <option value="zh-CN">简体中文</option>
        </select>
      </label>
      <p class="note">
        {app.state
          ? t("For this course: the interface and new teaching content. Sources and saved lessons keep their language.")
          : t("For this page. Each course keeps its own language once it is open.")}
      </p>
      {#if app.state}
        <label class="field">
          <span>{t("Daily reviews")}</span>
          <input
            class="count"
            type="number"
            min="1"
            max="20"
            step="1"
            bind:value={dailyReviews}
            onchange={changeDailyReviews}
            disabled={savingReviews}
          />
        </label>
        <p class="note">{t("At most this many sections come up for review each day; the rest wait for later days.")}</p>
        <div class="field">
          <span>{t("Teaching preferences")}</span>
          <div class="row">
            <span>{confirmedPreferences ? t("{count} confirmed", { count: confirmedPreferences }) : t("None yet")}</span>
            <button type="button" class="btn btn-quiet btn-small" onclick={openMemory}>{t("Open course memory")}</button>
          </div>
        </div>
        <p class="note">{t("Tell the teacher how you like to be taught; it asks before remembering it.")}</p>
      {/if}
    </section>

    <section aria-labelledby="teacher-title">
      <h3 id="teacher-title">{t("Teacher")}</h3>
      {#if settings}
        <form onsubmit={save}>
          <p class="note">{t("Lessons are taught by Codex on this computer, with your Codex sign-in.")}</p>
          <label class="field">
            <span>{t("Model")}</span>
            {#if models}
              <select bind:value={model}>
                <option value="">{t("Codex default")}</option>
                {#each choices(model) as option (option.id)}
                  <option value={option.id} title={option.description}>{option.name}</option>
                {/each}
              </select>
            {:else}
              <input type="text" bind:value={model} placeholder={t("Leave empty for your Codex default")} autocomplete="off" />
            {/if}
          </label>
          {#if !models}
            {#if modelsError}
              <p class="note">{t("Could not load models from Codex:")} {modelsError}</p>
            {:else}
              <p class="note" role="status">{t("Loading models from Codex…")}</p>
            {/if}
          {/if}
          <label class="field">
            <span>{t("Reasoning effort")}</span>
            <select bind:value={effort}>
              {#each teacherEfforts as option (option.id)}
                <option value={option.id}>{t(option.label)}</option>
              {/each}
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
          <!-- A saved small model or effort keeps the fold open, so a choice in effect is never hidden. -->
          <details open={!!(settings.small_model || settings.small_effort)}>
            <summary>{t("Advanced")}</summary>
            <div class="advanced">
              <p class="note">{t("The small model prepares upcoming sections and consolidates notes in the background.")}</p>
              <label class="field">
                <span>{t("Small model")}</span>
                {#if models}
                  <select bind:value={smallModel}>
                    <option value="">{t("Same as the teacher model")}</option>
                    {#each choices(smallModel) as option (option.id)}
                      <option value={option.id} title={option.description}>{option.name}</option>
                    {/each}
                  </select>
                {:else}
                  <input type="text" bind:value={smallModel} placeholder={t("Leave empty to use the teacher model")} autocomplete="off" />
                {/if}
              </label>
              <label class="field">
                <span>{t("Small model reasoning effort")}</span>
                <select bind:value={smallEffort}>
                  <option value="">{t("Same as the teacher")}</option>
                  {#each smallEfforts as option (option.id)}
                    <option value={option.id}>{t(option.label)}</option>
                  {/each}
                </select>
              </label>
            </div>
          </details>
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
  </div>

  <div id="settings-panel-about" role="tabpanel" aria-labelledby="settings-tab-about" hidden={tab !== 'about'}>
    <div class="identity">
      <img src="/favicon.svg" alt="" width="44" height="44" />
      <div>
        <p class="name">{t("Throughline")}</p>
        <p class="note">{about ? t("Version {version}", { version: about.version }) : '\u00a0'}</p>
      </div>
    </div>
    <p class="tagline">{t("One line of teaching through all your documents.")}</p>
    <p class="note">{t("A local study app that turns your PDFs and notes into a guided course. Codex teaches on this computer, with your own sign-in; your courses stay in your Throughline folder.")}</p>

    <section aria-labelledby="update-title">
      <h3 id="update-title">{t("Updates")}</h3>
      <div class="row">
        <button type="button" class="btn btn-quiet btn-small" onclick={checkForUpdates} disabled={checking}>
          {t(checking ? "Checking…" : "Check for updates")}
        </button>
        {#if update && !update.available}
          <span role="status">{t("You have the latest version.")}</span>
        {/if}
      </div>
      {#if update?.available}
        <p role="status">{t("Version {latest} is available.", { latest: update.latest })}</p>
        <div class="row">
          <CodexLink class="btn btn-primary btn-small" prompt={t("Update https://github.com/keweijun/throughline")}>{t("Update in Codex")}</CodexLink>
        </div>
        <p class="note">{t("Codex installs it and keeps your courses. Throughline closes while it updates; open it again afterwards.")}</p>
      {:else if updateError}
        <p class="note" role="status">{t("Could not check for updates:")} {updateError}</p>
      {/if}
    </section>

    <section aria-labelledby="credits-title">
      <h3 id="credits-title">{t("Credits")}</h3>
      <p>{t("Made by")} <a href="https://github.com/keweijun" target="_blank" rel="noreferrer">Keweijun</a></p>
      <p>
        <a href="https://github.com/keweijun/throughline" target="_blank" rel="noreferrer">{t("Source code on GitHub")}</a>
        · {t("MIT License")}
      </p>
      <p class="note">
        {t("Built with PDF.js, KaTeX, marked and DOMPurify, set in Source Serif 4 and IBM Plex Sans.")}
        <a href="https://github.com/keweijun/throughline/blob/main/THIRD_PARTY_LICENSES.md" target="_blank" rel="noreferrer">{t("Their licenses")}</a>
      </p>
    </section>
  </div>
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

  .tabs {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid var(--rule);
  }

  [role='tab'] {
    padding: 0.4rem 0.75rem;
    border: 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: none;
    color: var(--pencil);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  [role='tab'][aria-selected='true'] {
    border-bottom-color: var(--ink);
    color: var(--ink);
    font-weight: 600;
  }

  [role='tabpanel'] > section:first-child {
    border-top: 0;
  }

  [role='tabpanel']:not([hidden]) {
    display: grid;
    gap: 0.5rem;
  }

  #settings-panel-about {
    padding-top: 1rem;
  }

  .identity {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .name {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .tagline {
    font-family: var(--serif);
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

  .count {
    width: 5rem;
  }

  summary {
    cursor: pointer;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .advanced {
    display: grid;
    gap: 0.9rem;
    margin-top: 0.75rem;
  }

  .message {
    font-size: var(--step--1);
    color: var(--good);
  }
</style>
