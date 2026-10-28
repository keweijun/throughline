<script lang="ts">
  import { tick } from 'svelte';
  import { t, locale, type Language, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { CodexModel, Settings } from '../lib/types';

  type Theme = 'system' | 'light' | 'dark';
  type Pane = 'course' | 'teacher' | 'appearance';

  const MAX_DAILY_REVIEWS = 20;

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
  let dailyReviews = $state(5);
  let savingReviews = $state(false);
  let theme = $state<Theme>((document.documentElement.dataset.theme as Theme | undefined) ?? 'system');

  const settings = $derived(app.settings);
  // Without an open course there is nothing course-wide to set; the language then sits under Appearance, shown first.
  const panes = $derived<{ id: Pane; label: MessageKey }[]>(
    app.state
      ? [{ id: 'course', label: 'Course' }, { id: 'teacher', label: 'Teacher' }, { id: 'appearance', label: 'Appearance' }]
      : [{ id: 'appearance', label: 'Appearance' }, { id: 'teacher', label: 'Teacher' }],
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
      teacherSaved = false;
      if (!panes.some((p) => p.id === pane)) pane = panes[0].id;
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function changeLanguage(language: Language) {
    savingLanguage = true;
    await app.setLanguage(language);
    savingLanguage = false;
  }

  async function saveDailyReviews(value: number) {
    const saved = app.state?.preferences.daily_reviews ?? 5;
    if (!Number.isInteger(value) || value < 1 || value > MAX_DAILY_REVIEWS) {
      dailyReviews = saved;
      return;
    }
    dailyReviews = value;
    if (value === saved) return;
    savingReviews = true;
    dailyReviews = (await app.savePreferences({ daily_reviews: value }))?.daily_reviews ?? saved;
    savingReviews = false;
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
    const result = await app.act(() => api.put<Settings>('/api/settings', {
      model,
      small_model: smallModel,
      effort,
      small_effort: smallEffort,
      // A teacher model without a Fast tier runs at the standard speed.
      service_tier: models && !fastTier ? '' : serviceTier,
    }));
    savingTeacher = false;
    if (result) {
      app.settings = result;
      teacherSaved = true;
    }
  }
</script>

{#snippet icon(id: Pane)}
  <span class="glyph" aria-hidden="true">
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      {#if id === 'course'}
        <path d="M10 5.6C8.4 4.3 6.1 4 3.3 4.6v10.2c2.8-.6 5.1-.3 6.7 1 1.6-1.3 3.9-1.6 6.7-1V4.6C13.9 4 11.6 4.3 10 5.6zM10 5.6v10.2" />
      {:else if id === 'teacher'}
        <path d="M10 4.2 2.6 7.6 10 11l7.4-3.4zM5.6 9.2v3.4c1.2 1.3 2.7 1.9 4.4 1.9s3.2-.6 4.4-1.9V9.2M17.4 7.6v4.2" />
      {:else}
        <circle cx="10" cy="10" r="6.6" /><path d="M10 3.4a6.6 6.6 0 0 1 0 13.2z" fill="currentColor" stroke="none" />
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
        </button>
      {/each}
      <p class="scope">
        {pane === 'course'
          ? t("Saved in this course.")
          : pane === 'teacher'
            ? t("Saved for your user account, for every course.")
            : t("Saved in this browser.")}
      </p>
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
            <label class="title" for="daily-reviews">{t("Daily reviews")}</label>
            <p>{t("At most this many sections come up for review each day; the rest wait for later days.")}</p>
          </div>
          <div class="stepper">
            <button class="btn btn-quiet" aria-label={t("Fewer")} disabled={savingReviews || dailyReviews <= 1} onclick={() => saveDailyReviews(dailyReviews - 1)}>−</button>
            <input
              id="daily-reviews"
              type="number"
              min="1"
              max={MAX_DAILY_REVIEWS}
              step="1"
              bind:value={dailyReviews}
              onchange={() => saveDailyReviews(dailyReviews)}
              disabled={savingReviews}
            />
            <button class="btn btn-quiet" aria-label={t("More")} disabled={savingReviews || dailyReviews >= MAX_DAILY_REVIEWS} onclick={() => saveDailyReviews(dailyReviews + 1)}>+</button>
          </div>
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
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 6px;
    color: var(--pencil);
    transition:
      background-color var(--quick) var(--ease-out),
      color var(--quick) var(--ease-out);
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

  .stepper {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .stepper .btn {
    width: 2rem;
    padding: 0.35rem 0;
    justify-content: center;
    border-radius: 0;
  }

  .stepper input {
    width: 3rem;
    padding: 0.35rem 0;
    border: 0;
    border-inline: 1px solid var(--rule);
    border-radius: 0;
    text-align: center;
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .stepper input::-webkit-inner-spin-button,
  .stepper input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
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
