<script lang="ts">
  import { tick } from 'svelte';
  import { t, locale, type Language, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';
  import { exportNotes } from '../lib/notes';
  import type { CodexModel, Settings } from '../lib/types';
  import CodexLink from './CodexLink.svelte';

  type Theme = 'system' | 'light' | 'dark';
  type Pane = 'course' | 'teacher' | 'appearance' | 'about';


  let dialog: HTMLDialogElement | undefined = $state();
  let pane = $state<Pane>('course');
  let model = $state('');
  let smallModel = $state('');
  let serviceTier = $state('');
  let models = $state<CodexModel[] | null>(null);
  let modelsError = $state('');
  let effort = $state<Settings['effort']>('medium');
  let smallEffort = $state<Settings['small_effort']>('');
  let teacherSaved = $state(false);
  let savingTeacher = $state(false);
  let savingLanguage = $state(false);
  let about = $state<{ version: string } | null>(null);
  let updateError = $state('');
  let checking = $state(false);
  let savingAccess = $state(false);
  // Studio's access belongs to the learner; read when the Teacher pane opens, since on Windows it depends on Codex.
  $effect(() => {
    if (pane === 'teacher' && app.settingsOpen) void studio.loadAccess();
  });

  async function setFullAccess(on: boolean) {
    savingAccess = true;
    try {
      await studio.setFullAccess(on);
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    savingAccess = false;
  }
  let theme = $state<Theme>((document.documentElement.dataset.theme as Theme | undefined) ?? 'system');

  const settings = $derived(app.settings);
  // Without an open course there is nothing course-wide to set; the language then sits under Appearance, shown first.
  const panes = $derived<{ id: Pane; label: MessageKey }[]>(
    app.state
      ? [{ id: 'course', label: 'Course' }, { id: 'teacher', label: 'Teacher' }, { id: 'appearance', label: 'Appearance' }, { id: 'about', label: 'About' }]
      : [{ id: 'appearance', label: 'Appearance' }, { id: 'teacher', label: 'Teacher' }, { id: 'about', label: 'About' }],
  );
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

  // Offer only the reasoning efforts the chosen model supports, or all of them when Codex cannot list models.
  const EFFORTS: { id: Settings['effort']; label: MessageKey }[] = [
    { id: 'minimal', label: 'Minimal' },
    { id: 'low', label: 'Low' },
    { id: 'medium', label: 'Medium' },
    { id: 'high', label: 'High' },
    { id: 'xhigh', label: 'Extra high' },
    { id: 'max', label: 'Max' },
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

  async function loadAbout() {
    if (about) return;
    try {
      about = await api.get<{ version: string }>('/api/about');
    } catch {
      // The pane still works without the version.
    }
  }

  async function checkForUpdates() {
    checking = true;
    updateError = '';
    try {
      await app.checkForUpdate(true);
    } catch (error) {
      updateError = error instanceof Error ? error.message : String(error);
    }
    checking = false;
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
      void loadAbout();
      effort = settings?.effort ?? 'medium';
      smallEffort = settings?.small_effort ?? '';
      teacherSaved = false;
      const asked = panes.find((p) => p.id === app.settingsPane);
      app.settingsPane = null;
      if (asked) pane = asked.id;
      else if (!panes.some((p) => p.id === pane)) pane = panes[0].id;
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function changeLanguage(language: Language) {
    savingLanguage = true;
    await app.setLanguage(language);
    savingLanguage = false;
  }

  const notes = $derived(app.state?.annotations.length ?? 0);
  let exporting = $state(false);

  async function exportAll() {
    exporting = true;
    await exportNotes();
    exporting = false;
  }

  function openMemory() {
    app.settingsOpen = false;
    app.openPanel('memory');
  }

  function changeTheme(next: Theme) {
    theme = next;
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

  // Every teacher choice saves at once, after a new model has settled the effort it supports. Saves run one at a
  // time, each sending the choices as they are when it starts, so a quick series of changes ends with the last.
  let queue = Promise.resolve();
  function saveTeacher() {
    queue = queue.then(sendTeacher);
    return queue;
  }

  async function sendTeacher() {
    await tick();
    savingTeacher = true;
    teacherSaved = false;
    const result = await app.saveSettings({
      model,
      small_model: smallModel,
      effort,
      small_effort: smallEffort,
      // A teacher model without a Fast tier runs at the standard speed.
      service_tier: models && !fastTier ? '' : serviceTier,
    });
    savingTeacher = false;
    teacherSaved = !!result;
  }
</script>

{#snippet icon(id: Pane)}
  <!-- One 24-unit grid and one stroke weight, so the four read as a set. -->
  <span class="glyph" aria-hidden="true">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      {#if id === 'course'}
        <path d="M3.5 5.6c3.2-.6 6-.1 8.5 1.8 2.5-1.9 5.3-2.4 8.5-1.8v12.2c-3.2-.6-6-.1-8.5 1.8-2.5-1.9-5.3-2.4-8.5-1.8zM12 7.4v12.2" />
      {:else if id === 'teacher'}
        <path d="M12 4.5 2.5 9 12 13.5 21.5 9zM6.5 11.2v4.4c1.6 1.6 3.4 2.4 5.5 2.4s3.9-.8 5.5-2.4v-4.4M21.5 9v5.5" />
      {:else if id === 'about'}
        <circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.2" /><circle cx="12" cy="7.9" r="1.1" fill="currentColor" stroke="none" />
      {:else}
        <path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.1 0 1.8-.7 1.8-1.6 0-.5-.2-.9-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1 .8-1.7 1.8-1.7h2.2a4.2 4.2 0 0 0 4.2-4.2c0-3.8-4-6.9-9-6.9z" />
        <circle cx="7.6" cy="11.4" r="1.1" fill="currentColor" stroke="none" /><circle cx="9.9" cy="7.7" r="1.1" fill="currentColor" stroke="none" /><circle cx="14.4" cy="7.6" r="1.1" fill="currentColor" stroke="none" />
      {/if}
    </svg>
  </span>
{/snippet}

{#snippet languageChoice()}
  <div class="segmented" role="radiogroup" aria-label={t("Language")}>
    {#each [['en', 'English'], ['zh-CN', '简体中文']] as [id, name] (id)}
      <label>
        <input
          type="radio"
          name="language"
          value={id}
          checked={locale.language === id}
          disabled={savingLanguage}
          onchange={() => changeLanguage(id as Language)}
        />{name}
      </label>
    {/each}
  </div>
{/snippet}

<dialog bind:this={dialog} onclose={() => (app.settingsOpen = false)} aria-labelledby="settings-title">
  <header>
    <h2 id="settings-title">{t("Settings")}</h2>
    <button class="btn btn-quiet close" onclick={() => (app.settingsOpen = false)} aria-label={t("Close")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
    </button>
  </header>

  <div class="body">
    <nav aria-label={t("Settings")}>
      {#each panes as item (item.id)}
        <button class="category" aria-current={pane === item.id ? 'page' : undefined} onclick={() => (pane = item.id)}>
          {@render icon(item.id)}{t(item.label)}
          {#if item.id === 'about' && app.update?.available}<span class="tag">{t("Update")}</span>{/if}
        </button>
      {/each}
      {#if pane !== 'about'}
        <p class="scope">
          {pane === 'course'
            ? t("Saved in this course.")
            : pane === 'teacher'
              ? t("Saved for your user account, for every course.")
              : t("Saved in this browser.")}
        </p>
      {/if}
    </nav>

    <div class="pane">
      {#if pane === 'course' && app.state}
        <h3>{t("Course")}</h3>
        <div class="setting">
          <div class="text">
            <span class="title">{t("Language")}</span>
            <p>{t("The interface and new teaching content. Sources and saved lessons keep their language.")}</p>
          </div>
          {@render languageChoice()}
        </div>
        <div class="setting">
          <div class="text">
            <span class="title">{t("Teaching preferences")}</span>
            <p>
              {confirmedPreferences ? t("{count} confirmed", { count: confirmedPreferences }) : t("None yet")}.
              {t("Tell the teacher how you like to be taught; it asks before remembering it.")}
            </p>
          </div>
          <button class="btn btn-small" onclick={openMemory}>{t("Open course memory")}</button>
        </div>
        <div class="setting">
          <div class="text">
            <span class="title">{t("Your notes")}</span>
            <p>
              {notes === 1 ? t("1 highlight, note or bookmark") : t("{count} highlights, notes and bookmarks", { count: notes })}.
              {t("Export them as one Markdown file, by chapter and section; notes with images come as a ZIP with an images folder.")}
            </p>
          </div>
          <button class="btn btn-small" disabled={!notes || exporting} onclick={exportAll}>{exporting ? t("Exporting…") : t("Export notes")}</button>
        </div>
      {:else if pane === 'teacher'}
        <h3>{t("Teacher")}</h3>
        <p class="lead">{t("Lessons are taught by Codex on this computer, with your Codex sign-in.")}</p>
        {#if settings}
          <div class="setting">
            <div class="text">
              <label class="title" for="teacher-model">{t("Model")}</label>
              {#if !models}
                <p role="status">{modelsError ? `${t("Could not load models from Codex:")} ${modelsError}` : t("Loading models from Codex…")}</p>
              {/if}
            </div>
            {#if models}
              <select id="teacher-model" bind:value={model} onchange={saveTeacher}>
                <option value="">{t("Codex default")}</option>
                {#each choices(model) as option (option.id)}
                  <option value={option.id} title={option.description}>{option.name}</option>
                {/each}
              </select>
            {:else}
              <input id="teacher-model" type="text" bind:value={model} onchange={saveTeacher} placeholder={t("Codex default")} autocomplete="off" />
            {/if}
          </div>
          <div class="setting">
            <div class="text">
              <span class="title">{t("Reasoning effort")}</span>
              <p>{t("More effort gives more careful answers, and takes longer.")}</p>
            </div>
            <div class="segmented" role="radiogroup" aria-label={t("Reasoning effort")}>
              {#each teacherEfforts as option (option.id)}
                <label><input type="radio" name="effort" value={option.id} bind:group={effort} onchange={saveTeacher} />{t(option.label)}</label>
              {/each}
            </div>
          </div>
          {#if fastId}
            <div class="setting">
              <div class="text">
                <label class="title" for="fast-mode">{t("Fast mode")}</label>
                <p>{fastTier?.description ? `${fastTier.description}. ` : ''}{t("Applies to lessons, answers and feedback; background preparation keeps the standard speed.")}</p>
              </div>
              <input
                id="fast-mode"
                class="switch"
                type="checkbox"
                role="switch"
                checked={serviceTier === fastId}
                onchange={(event) => {
                  serviceTier = event.currentTarget.checked ? fastId : '';
                  void saveTeacher();
                }}
              />
            </div>
          {/if}

          <h4>{t("Studio")}</h4>
          <p class="lead">{t("Studio is where Codex creates and changes your courses. It reads any file you point it to and writes inside your Throughline folder without asking.")}</p>
          <div class="setting">
            <div class="text">
              <label class="title" for="full-access">{t("Full access")}</label>
              <p>
                {#if studio.access?.forced}
                  {t("Codex's sandbox is not set up on this Windows computer, so Studio runs with full access, as Codex does here.")}
                {:else}
                  {t("Let Codex change files anywhere and run commands without asking, as Codex can in its own app. Off, it asks before writing outside your Throughline folder or using the network.")}
                {/if}
              </p>
            </div>
            <input
              id="full-access"
              class="switch"
              type="checkbox"
              role="switch"
              checked={studio.access?.full_access ?? false}
              disabled={!studio.access || studio.access.forced || savingAccess}
              onchange={(event) => void setFullAccess(event.currentTarget.checked)}
            />
          </div>

          <h4>{t("Background work")}</h4>
          <p class="lead">{t("The small model prepares upcoming sections and consolidates notes in the background.")}</p>
          <div class="setting">
            <div class="text"><label class="title" for="small-model">{t("Small model")}</label></div>
            {#if models}
              <select id="small-model" bind:value={smallModel} onchange={saveTeacher}>
                <option value="">{t("Same as the teacher model")}</option>
                {#each choices(smallModel) as option (option.id)}
                  <option value={option.id} title={option.description}>{option.name}</option>
                {/each}
              </select>
            {:else}
              <input id="small-model" type="text" bind:value={smallModel} onchange={saveTeacher} placeholder={t("Same as the teacher model")} autocomplete="off" />
            {/if}
          </div>
          <div class="setting">
            <div class="text"><label class="title" for="small-effort">{t("Small model reasoning effort")}</label></div>
            <select id="small-effort" bind:value={smallEffort} onchange={saveTeacher}>
              <option value="">{t("Same as the teacher")}</option>
              {#each smallEfforts as option (option.id)}
                <option value={option.id}>{t(option.label)}</option>
              {/each}
            </select>
          </div>

          <div class="foot">
            {#if savingTeacher}
              <span role="status">{t("Saving…")}</span>
            {:else if teacherSaved}
              <span class="saved" role="status">{t("Saved. New lessons, answers and feedback use these settings.")}</span>
            {/if}
            {#if settings.overridden}
              <p>{t("This host was started with model or effort options. Changes here replace them.")}</p>
            {/if}
            <p>{t("Saved in")} <code>{settings.path}</code>{t(", never inside a course folder.")}</p>
          </div>
        {/if}
      {:else if pane === 'about'}
        <div class="identity">
          <img src="/favicon.svg" alt="" width="48" height="48" />
          <div>
            <h3>{t("Throughline")}</h3>
            <p class="lead">{about ? t("Version {version}", { version: about.version }) : '\u00a0'}</p>
          </div>
        </div>
        <p class="tagline">{t("One line of teaching through all your documents.")}</p>
        <p class="lead">{t("A local study app that turns your PDFs and notes into a guided course. Codex teaches on this computer, with your own sign-in; your courses stay in your Throughline folder.")}</p>
        <div class="setting">
          <div class="text">
            <span class="title">{t("Updates")}</span>
            {#if app.update?.available}
              <p role="status">{t("Version {latest} is available.", { latest: app.update.latest })} {t("Codex installs it and keeps your courses. Throughline closes while it updates; open it again afterwards.")}</p>
            {:else if updateError}
              <p role="status">{t("Could not check for updates:")} {updateError}</p>
            {:else if app.update}
              <p role="status">{t("You have the latest version.")}</p>
            {/if}
          </div>
          {#if app.update?.available}
            <CodexLink chat class="btn btn-primary btn-small" prompt={t("Update https://github.com/keweijun/throughline")}>{t("Update in Codex")}</CodexLink>
          {:else}
            <button class="btn btn-small" onclick={checkForUpdates} disabled={checking}>{t(checking ? "Checking…" : "Check for updates")}</button>
          {/if}
        </div>

        <h4>{t("Credits")}</h4>
        <div class="credits">
          <p>{t("Made by")} <a href="https://github.com/keweijun" target="_blank" rel="noreferrer">Keweijun</a></p>
          <p><a href="https://github.com/keweijun/throughline" target="_blank" rel="noreferrer">{t("Source code on GitHub")}</a> · {t("MIT License")}</p>
          <p class="lead">
            {t("Built with PDF.js, KaTeX, marked and DOMPurify, set in Source Serif 4 and IBM Plex Sans.")}
            <a href="https://github.com/keweijun/throughline/blob/main/THIRD_PARTY_LICENSES.md" target="_blank" rel="noreferrer">{t("Their licenses")}</a>
          </p>
        </div>
      {:else}
        <h3>{t("Appearance")}</h3>
        {#if !app.state}
          <div class="setting">
            <div class="text">
              <span class="title">{t("Language")}</span>
              <p>{t("For this page. Each course keeps its own language once it is open.")}</p>
            </div>
            {@render languageChoice()}
          </div>
        {/if}
        <div class="setting stacked">
          <div class="text"><span class="title">{t("Theme")}</span></div>
          <div class="themes" role="radiogroup" aria-label={t("Theme")}>
            {#each [['system', 'Match the system'], ['light', 'Light'], ['dark', 'Dark']] as const as [id, label] (id)}
              <label class="theme">
                <input type="radio" name="theme" value={id} checked={theme === id} onchange={() => changeTheme(id)} />
                <span class="swatch {id}" aria-hidden="true"></span>
                {t(label)}
              </label>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
</dialog>

<style>
  dialog {
    width: min(54rem, calc(100vw - 2rem));
    height: min(38rem, calc(100vh - 4rem));
    padding: 0;
    border: 1px solid var(--rule);
    border-radius: 12px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  dialog[open] {
    display: flex;
    flex-direction: column;
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.45);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem 1rem 1.5rem;
    border-bottom: 1px solid var(--rule);
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  .close {
    padding: 0.35rem;
  }

  .body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 13rem 1fr;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 1rem 0.75rem;
    border-right: 1px solid var(--rule);
    background: var(--ground);
  }

  .category {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.4rem 0.6rem 0.4rem 0.4rem;
    border: 1px solid transparent;
    border-radius: 8px;
    background: none;
    color: var(--ink-soft);
    font: inherit;
    text-align: start;
    cursor: pointer;
    transition:
      background-color var(--quick) var(--ease-out),
      border-color var(--quick) var(--ease-out),
      color var(--quick) var(--ease-out);
  }

  .glyph {
    display: grid;
    place-items: center;
    flex: none;
    width: 2rem;
    height: 2rem;
    border-radius: 8px;
    background: color-mix(in srgb, var(--ink) 6%, transparent);
    color: var(--ink-soft);
    transition:
      background-color var(--quick) var(--ease-out),
      color var(--quick) var(--ease-out);
  }

  .tag {
    margin-inline-start: auto;
    padding: 0.05rem 0.45rem;
    border-radius: 999px;
    background: var(--accent-wash);
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 600;
  }

  .category:hover {
    background: color-mix(in srgb, var(--ink) 5%, transparent);
    color: var(--ink);
  }

  .category:hover .glyph {
    color: var(--ink);
  }

  /* The open category reads as a raised sheet with a filled icon tile, matching the pane it opens. */
  .category[aria-current='page'] {
    border-color: var(--rule);
    background: var(--sheet);
    color: var(--ink);
    font-weight: 600;
    box-shadow: 0 1px 2px var(--shadow-near);
  }

  .category[aria-current='page'] .glyph {
    background: var(--accent);
    color: var(--on-accent);
  }

  @media (prefers-reduced-motion: reduce) {
    .category,
    .glyph {
      transition: none;
    }
  }

  .scope {
    margin-top: auto;
    padding: 0.75rem 0.75rem 0;
    border-top: 1px solid var(--rule);
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .pane {
    overflow-y: auto;
    padding: 1.25rem 1.75rem 1.75rem;
  }

  h3 {
    font-size: var(--step-1);
    font-weight: 600;
    margin-bottom: 0.25rem;
  }

  h4 {
    margin-top: 1.75rem;
    font-size: var(--step-0);
    font-weight: 600;
  }

  .lead {
    font-size: var(--step--1);
    color: var(--pencil);
    margin-bottom: 0.25rem;
  }

  .identity {
    display: flex;
    align-items: center;
    gap: 0.9rem;
  }

  .identity h3 {
    font-family: var(--serif);
    margin-bottom: 0;
  }

  .tagline {
    margin-top: 1rem;
    font-family: var(--serif);
  }

  .credits {
    display: grid;
    gap: 0.4rem;
    margin-top: 0.5rem;
  }

  .setting {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.5rem 1.5rem;
    padding-block: 1rem;
    border-bottom: 1px solid var(--rule);
  }

  .setting.stacked {
    grid-template-columns: 1fr;
    border-bottom: 0;
  }

  .setting > select,
  .setting > input[type='text'] {
    width: 15rem;
  }

  .title {
    font-weight: 500;
  }

  .text p {
    margin-top: 0.15rem;
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  .switch {
    appearance: none;
    position: relative;
    width: 2.5rem;
    height: 1.4rem;
    margin: 0;
    border-radius: 999px;
    background: var(--rule-strong);
    cursor: pointer;
    transition: background var(--quick) var(--ease-out);
  }

  .switch::after {
    content: '';
    position: absolute;
    top: 0.2rem;
    left: 0.2rem;
    width: 1rem;
    height: 1rem;
    border-radius: 50%;
    background: var(--raised);
    box-shadow: 0 1px 2px var(--shadow-far);
    transition: transform var(--quick) var(--ease-out);
  }

  .switch:checked {
    background: var(--accent);
  }

  .switch:checked::after {
    transform: translateX(1.1rem);
  }

  .themes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }

  .theme {
    position: relative;
    display: grid;
    gap: 0.6rem;
    padding: 0.75rem;
    border: 1px solid var(--rule);
    border-radius: 8px;
    background: var(--raised);
    color: var(--ink-soft);
    font-weight: 500;
    cursor: pointer;
  }

  .theme:hover {
    border-color: var(--rule-strong);
  }

  .theme:has(input:checked) {
    border-color: var(--accent);
    color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }

  .theme:has(input:focus-visible) {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .theme input {
    position: absolute;
    opacity: 0;
  }

  .swatch {
    height: 3.5rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
  }

  .swatch.light {
    background: linear-gradient(#eef1f5 0 30%, #fbfcfd 30%);
  }

  .swatch.dark {
    background: linear-gradient(#11141b 0 30%, #171b24 30%);
  }

  .swatch.system {
    background: linear-gradient(135deg, #fbfcfd 50%, #171b24 50%);
  }

  .foot {
    display: grid;
    gap: 0.35rem;
    margin-top: 1.25rem;
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  .saved {
    color: var(--good);
  }

  @media (max-width: 40rem) {
    .body {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
    }

    nav {
      flex-direction: row;
      border-right: 0;
      border-bottom: 1px solid var(--rule);
    }

    .scope {
      display: none;
    }
  }
</style>
