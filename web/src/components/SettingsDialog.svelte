<script lang="ts">
  import { tick } from 'svelte';
  import { t, locale, type Language, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { CodexModel, LauncherStatus, Settings, UpdateProgress } from '../lib/types';
  import CodexLink from './CodexLink.svelte';
  import LauncherHelp from './LauncherHelp.svelte';
  import Activity from './Activity.svelte';
  import { lightDismiss } from '../lib/dialog';
  import { notifications, refreshNotifications, setNotifications } from '../lib/notify.svelte';

  type Theme = 'system' | 'light' | 'dark';
  type Reading = 'small' | 'default' | 'large' | 'larger';
  type Pane = 'teacher' | 'appearance' | 'activity' | 'about';
  type Group = 'teaching' | 'background';

  let dialog: HTMLDialogElement | undefined = $state();
  let pane = $state<Pane>('appearance');
  let model = $state('');
  let smallModel = $state('');
  let serviceTier = $state('');
  let models = $state<CodexModel[] | null>(null);
  let modelsError = $state('');
  let effort = $state<Settings['effort']>('medium');
  let smallEffort = $state<Settings['small_effort']>('');
  // The group whose change is saving or was last saved, so the word shows beside what was changed.
  let savedGroup = $state<Group | null>(null);
  let savingTeacher = $state(false);
  let savingLanguage = $state(false);
  let about = $state<{ version: string } | null>(null);
  let launcher = $state<LauncherStatus | null>(null);
  let updateError = $state('');
  let checking = $state(false);
  let theme = $state<Theme>((document.documentElement.dataset.theme as Theme | undefined) ?? 'system');
  let reading = $state<Reading>((document.documentElement.dataset.reading as Reading | undefined) ?? 'default');
  const READING: { id: Reading; label: MessageKey }[] = [
    { id: 'small', label: 'Small' },
    { id: 'default', label: 'Default' },
    { id: 'large', label: 'Large' },
    { id: 'larger', label: 'Larger' },
  ];
  let notifying = $state(false);
  let paneElement: HTMLDivElement | undefined = $state();
  // Each category opens at its top, not where the last one was scrolled to.
  $effect(() => {
    void pane;
    if (paneElement) paneElement.scrollTop = 0;
  });
  let opening = $state(false);

  const settings = $derived(app.settings);
  // Settings hold only what applies to every course; the course's own things are in Studio and on its card in the
  // library (ADR 0017).
  const panes: { id: Pane; label: MessageKey }[] = [
    { id: 'appearance', label: 'Appearance' },
    { id: 'teacher', label: 'Teacher' },
    { id: 'activity', label: 'Activity' },
    { id: 'about', label: 'About' },
  ];
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
  // The model background work actually runs on: unset means the default small model, 'teacher' the teacher's own.
  const effectiveSmall = $derived(smallModel === 'teacher' ? model : smallModel || 'gpt-6.1-terra');
  const smallEfforts = $derived(effortsFor(effectiveSmall));
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
    try {
      launcher = await api.get<LauncherStatus>('/api/launcher');
    } catch {
      // Nor does it need the launcher.
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

  const updating = $derived(app.updating);
  let starting = $state(false);
  const UPDATE_STEP: Record<UpdateProgress['step'], MessageKey> = {
    starting: 'Codex is getting ready to install version {version}…',
    installing: 'Installing version {version}…',
    restarting: 'Starting Throughline again…',
    done: 'Updated. Reloading…',
  };

  async function installUpdate() {
    starting = true;
    try {
      await app.installUpdate(locale.language);
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    starting = false;
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
      refreshNotifications();
      effort = settings?.effort ?? 'medium';
      smallEffort = settings?.small_effort ?? '';
      savedGroup = null;
      const asked = panes.find((p) => p.id === app.settingsPane);
      app.settingsPane = null;
      if (asked) pane = asked.id;
      else if (!panes.some((p) => p.id === pane)) pane = panes[0].id;
      if (paneElement) paneElement.scrollTop = 0;
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function changeLanguage(language: Language) {
    savingLanguage = true;
    await app.setLanguage(language);
    savingLanguage = false;
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

  function changeReading(next: Reading) {
    reading = next;
    const root = document.documentElement;
    if (reading === 'default') delete root.dataset.reading;
    else root.dataset.reading = reading;
    try {
      if (reading === 'default') localStorage.removeItem('reading');
      else localStorage.setItem('reading', reading);
    } catch {
      // The choice still applies for this visit.
    }
  }

  async function changeNotifications(on: boolean) {
    notifying = true;
    await setNotifications(on);
    notifying = false;
  }

  async function showFolder() {
    opening = true;
    try {
      await api.post('/api/library/show');
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    }
    opening = false;
  }

  // Every teacher choice saves at once, after a new model has settled the effort it supports. Saves run one at a
  // time, each sending the choices as they are when it starts, so a quick series of changes ends with the last.
  let queue = Promise.resolve();
  function saveTeacher(group: Group) {
    savedGroup = group;
    queue = queue.then(sendTeacher);
    return queue;
  }

  async function sendTeacher() {
    await tick();
    savingTeacher = true;
    const result = await app.saveSettings({
      model,
      small_model: smallModel,
      effort,
      small_effort: smallEffort,
      // A teacher model without a Fast tier runs at the standard speed.
      service_tier: models && !fastTier ? '' : serviceTier,
    });
    savingTeacher = false;
    if (!result) savedGroup = null;
  }
</script>

{#snippet icon(id: Pane)}
  <!-- One 24-unit grid and one stroke weight, so the four read as a set. -->
  <span class="glyph" aria-hidden="true">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      {#if id === 'teacher'}
        <path d="M12 4.5 2.5 9 12 13.5 21.5 9zM6.5 11.2v4.4c1.6 1.6 3.4 2.4 5.5 2.4s3.9-.8 5.5-2.4v-4.4M21.5 9v5.5" />
      {:else if id === 'activity'}
        <rect x="3.5" y="5" width="17" height="15" rx="2.5" /><path d="M3.5 9.5h17M8 3v4M16 3v4" />
        <rect x="7" y="12.5" width="3" height="3" rx=".6" fill="currentColor" stroke="none" /><rect x="11.5" y="12.5" width="3" height="3" rx=".6" fill="currentColor" stroke="none" opacity=".45" />
      {:else if id === 'about'}
        <circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.2" /><circle cx="12" cy="7.9" r="1.1" fill="currentColor" stroke="none" />
      {:else}
        <path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.1 0 1.8-.7 1.8-1.6 0-.5-.2-.9-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1 .8-1.7 1.8-1.7h2.2a4.2 4.2 0 0 0 4.2-4.2c0-3.8-4-6.9-9-6.9z" />
        <circle cx="7.6" cy="11.4" r="1.1" fill="currentColor" stroke="none" /><circle cx="9.9" cy="7.7" r="1.1" fill="currentColor" stroke="none" /><circle cx="14.4" cy="7.6" r="1.1" fill="currentColor" stroke="none" />
      {/if}
    </svg>
  </span>
{/snippet}

{#snippet saveStatus(group: Group)}
  {#if savedGroup === group}
    {#if savingTeacher}
      <span class="status" role="status">{t("Saving…")}</span>
    {:else}
      <span class="status saved" role="status">{t("Saved")}</span>
    {/if}
  {/if}
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

<dialog bind:this={dialog} use:lightDismiss onclose={() => (app.settingsOpen = false)} aria-labelledby="settings-title">
  <button class="btn btn-quiet close" onclick={() => (app.settingsOpen = false)} aria-label={t("Close")}>
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
  </button>

  <!-- Four levels, each a step quieter than the one above: the dialog's name over its categories, the open
       category's title, a group's label over its card, and each row's title over its description. -->
  <nav aria-label={t("Settings")}>
    <h2 id="settings-title">{t("Settings")}</h2>
    {#each panes as item (item.id)}
      <button class="category" aria-current={pane === item.id ? 'page' : undefined} onclick={() => (pane = item.id)}>
        {@render icon(item.id)}{t(item.label)}
        {#if item.id === 'about' && app.update?.available}<span class="tag">{t("Update")}</span>{/if}
      </button>
    {/each}
  </nav>

  <div class="pane" bind:this={paneElement}>
    {#if pane === 'teacher'}
      <div class="head">
        <h3>{t("Teacher")}</h3>
        <p class="lead">{t("Lessons are taught by Codex on this computer, with your Codex sign-in.")}</p>
      </div>
      {#if settings}
        <section class="group" aria-labelledby="group-teaching">
          <div class="label">
            <h4 id="group-teaching">{t("Lessons and answers")}</h4>
            {@render saveStatus('teaching')}
          </div>
          <!-- The teacher's model and the small model are set alike: a model, then its reasoning effort under it. -->
          <p class="note above">{t("Lessons, side answers and feedback on your answers.")}</p>
          <div class="card">
            <div class="setting">
              <div class="text">
                <label class="title" for="teacher-model">{t("Model")}</label>
                {#if !models}
                  <p role="status">{modelsError ? `${t("Could not load models from Codex:")} ${modelsError}` : t("Loading models from Codex…")}</p>
                {/if}
              </div>
              {#if models}
                <select id="teacher-model" bind:value={model} onchange={() => saveTeacher('teaching')}>
                  <option value="">{t("Codex default")}</option>
                  {#each choices(model) as option (option.id)}
                    <option value={option.id} title={option.description}>{option.name}</option>
                  {/each}
                </select>
              {:else}
                <input id="teacher-model" type="text" bind:value={model} onchange={() => saveTeacher('teaching')} placeholder={t("Codex default")} autocomplete="off" />
              {/if}
            </div>
            <div class="setting stacked">
              <div class="text">
                <span class="title" id="effort-title">{t("Reasoning effort")}</span>
                <p>{t("More effort gives more careful answers, and takes longer.")}</p>
              </div>
              <div class="segmented" role="radiogroup" aria-labelledby="effort-title">
                {#each teacherEfforts as option (option.id)}
                  <label><input type="radio" name="effort" value={option.id} bind:group={effort} onchange={() => saveTeacher('teaching')} />{t(option.label)}</label>
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
                    void saveTeacher('teaching');
                  }}
                />
              </div>
            {/if}
          </div>
        </section>

        <section class="group" aria-labelledby="group-studio">
          <div class="label"><h4 id="group-studio">{t("Studio")}</h4></div>
          <p class="note above">{t("Studio uses the teacher's model until you choose its own in Studio's writing box.")}</p>
          <div class="card">
            <div class="setting">
              <div class="text">
                <label class="title" for="notify-studio">{t("Notifications")}</label>
                {#if notifications.permission === 'denied'}
                  <p role="status">{t("Your browser blocks notifications from Throughline. Allow them in the browser's site settings, then turn this on.")}</p>
                {:else if notifications.permission === 'unsupported'}
                  <p>{t("This browser cannot show notifications.")}</p>
                {:else}
                  <p>{t("Tell me when Studio finishes or needs my answer while I'm in another tab or app. Saved in this browser.")}</p>
                {/if}
              </div>
              <input
                id="notify-studio"
                class="switch"
                type="checkbox"
                role="switch"
                checked={notifications.on}
                disabled={notifying || notifications.permission === 'denied' || notifications.permission === 'unsupported'}
                onchange={(event) => changeNotifications(event.currentTarget.checked)}
              />
            </div>
          </div>
        </section>

        <section class="group" aria-labelledby="group-background">
          <div class="label">
            <h4 id="group-background">{t("Background work")}</h4>
            {@render saveStatus('background')}
          </div>
          <p class="note above">{t("The small model prepares upcoming sections, consolidates notes in the background, and runs the quick teacher of drills in Review.")}</p>
          <div class="card">
            <div class="setting">
              <div class="text"><label class="title" for="small-model">{t("Small model")}</label></div>
              {#if models}
                <select id="small-model" bind:value={smallModel} onchange={() => saveTeacher('background')}>
                  <!-- Empty is Throughline's default small model; `teacher` the teacher's (background.small_model). -->
                  <option value="">{t("Default (GPT-6.1 Terra)")}</option>
                  <option value="teacher">{t("Same as the teacher model")}</option>
                  {#each choices(smallModel === "teacher" ? "" : smallModel) as option (option.id)}
                    <option value={option.id} title={option.description}>{option.name}</option>
                  {/each}
                </select>
              {:else}
                <input id="small-model" type="text" bind:value={smallModel} onchange={() => saveTeacher('background')} placeholder={t("Default: gpt-6.1-terra")} autocomplete="off" />
              {/if}
            </div>
            <div class="setting stacked">
              <!-- The group already says whose effort this is; the name keeps it apart from the teacher's. -->
              <div class="text"><span class="title">{t("Reasoning effort")}</span></div>
              <!-- Empty follows the teacher's effort. -->
              <div class="segmented" role="radiogroup" aria-label={t("Small model reasoning effort")}>
                <label><input type="radio" name="small-effort" value="" bind:group={smallEffort} onchange={() => saveTeacher('background')} />{t("Same as the teacher")}</label>
                {#each smallEfforts as option (option.id)}
                  <label><input type="radio" name="small-effort" value={option.id} bind:group={smallEffort} onchange={() => saveTeacher('background')} />{t(option.label)}</label>
                {/each}
              </div>
            </div>
          </div>
        </section>

        <div class="foot">
          {#if settings.overridden}
            <p>{t("This host was started with model or effort options. Changes here replace them.")}</p>
          {/if}
          <p>{t("Saved in")} <code>{settings.path}</code>{t(", never inside a course folder.")}</p>
        </div>
      {/if}
    {:else if pane === 'activity'}
      <Activity />
    {:else if pane === 'about'}
      <div class="head identity">
        <img src="/favicon.svg" alt="" width="44" height="44" />
        <div>
          <h3>{t("Throughline")}</h3>
          <p class="lead">{about ? t("Version {version}", { version: about.version }) : '\u00a0'}</p>
        </div>
      </div>
      <p class="tagline">{t("One line of teaching through all your documents.")}</p>
      <p class="blurb">{t("A local study app that turns your PDFs and notes into a guided course. Codex teaches on this computer, with your own sign-in; your courses stay in your Throughline folder.")}</p>

      <section class="group" aria-label={t("Updates and folder")}>
        <div class="card">
          <div class="setting">
            <div class="text">
              <span class="title">{t("Updates")}</span>
              {#if updating && !updating.failed}
                <p role="status">{t(UPDATE_STEP[updating.step], { version: updating.to })}</p>
              {:else if updating?.failed}
                <p role="status">{t("The update did not finish:")} {updating.failed}</p>
              {:else if app.updated && !app.update?.available}
                <p role="status">{t("Updated to version {version}. Your courses are as you left them.", { version: app.updated })}</p>
              {:else if app.update?.available}
                <p role="status">{t("Version {latest} is available.", { latest: app.update.latest })} {t("Codex installs it in the background and keeps your courses. Throughline closes for a minute or two and comes back by itself.")}</p>
              {:else if updateError}
                <p role="status">{t("Could not check for updates:")} {updateError}</p>
              {:else if app.update}
                <p role="status">{t("You have the latest version.")}</p>
              {/if}
            </div>
            {#if updating && !updating.failed}
              <span class="percent" aria-hidden="true">{Math.round(updating.progress)}%</span>
            {:else if app.update?.available || updating?.failed}
              <div class="update-actions">
                {#if updating?.failed}
                  <CodexLink chat class="btn btn-small" prompt={t("Update https://github.com/keweijun/throughline")}>{t("Update in Codex")}</CodexLink>
                {/if}
                <button class="btn btn-primary btn-small" onclick={installUpdate} disabled={starting}>{t(updating?.failed ? "Try again" : "Update")}</button>
              </div>
            {:else}
              <button class="btn btn-small" onclick={checkForUpdates} disabled={checking}>{t(checking ? "Checking…" : "Check for updates")}</button>
            {/if}
            {#if updating && !updating.failed}
              <div class="progress" role="progressbar" aria-label={t("Update progress")} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(updating.progress)}>
                <span style:width="{updating.progress}%"></span>
              </div>
            {/if}
          </div>
          {#if app.library?.root}
            <div class="setting">
              <div class="text">
                <span class="title">{t("Throughline folder")}</span>
                <p>{t("Your courses, each in its own folder.")} <code>{app.library.root}</code></p>
              </div>
              <button class="btn btn-small" onclick={showFolder} disabled={opening}>{t("Open folder")}</button>
            </div>
          {/if}
        </div>
      </section>

      {#if launcher}
        <section class="group" aria-labelledby="group-launcher">
          <div class="label"><h4 id="group-launcher">{t("Opening Throughline next time")}</h4></div>
          <LauncherHelp {launcher} />
        </section>
      {/if}

      <section class="group credits" aria-labelledby="group-credits">
        <div class="label"><h4 id="group-credits">{t("Credits")}</h4></div>
        <p>{t("Made by")} <a href="https://github.com/keweijun" target="_blank" rel="noreferrer">Keweijun</a> · <a href="https://github.com/keweijun/throughline" target="_blank" rel="noreferrer">{t("Source code on GitHub")}</a> · {t("MIT License")}</p>
        <p class="note">
          {t("Built with PDF.js, KaTeX, marked and DOMPurify, set in Source Serif 4 and IBM Plex Sans.")}
          <a href="https://github.com/keweijun/throughline/blob/main/THIRD_PARTY_LICENSES.md" target="_blank" rel="noreferrer">{t("Their licenses")}</a>
        </p>
      </section>
    {:else}
      <div class="head">
        <h3>{t("Appearance")}</h3>
      </div>
      <section class="group" aria-label={t("Appearance")}>
        <div class="card">
          <div class="setting">
            <div class="text">
              <span class="title">{t("Language")}</span>
              <p>
                {app.state
                  ? t("The interface, and new teaching in this course. Sources and saved lessons keep their language.")
                  : t("For this page. Each course keeps its own language once it is open.")}
              </p>
            </div>
            {@render languageChoice()}
          </div>
          <div class="setting">
            <div class="text">
              <span class="title">{t("Text size")}</span>
              <p>{t("For lessons, exercises, key points and notes. Saved in this browser.")}</p>
            </div>
            <div class="segmented" role="radiogroup" aria-label={t("Text size")}>
              {#each READING as option (option.id)}
                <label><input type="radio" name="reading" value={option.id} checked={reading === option.id} onchange={() => changeReading(option.id)} />{t(option.label)}</label>
              {/each}
            </div>
          </div>
          <div class="setting stacked">
            <div class="text">
              <span class="title">{t("Theme")}</span>
              <p>{t("Saved in this browser.")}</p>
            </div>
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
        </div>
      </section>
    {/if}
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
    display: grid;
    grid-template-columns: 13.5rem minmax(0, 1fr);
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.45);
  }

  .close {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    z-index: 1;
    padding: 0.35rem;
  }

  /* Rows scroll under it, so it keeps the sheet behind it. */
  .close:not(:hover) {
    background: var(--sheet);
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    padding: 1.25rem 0.75rem 1rem;
    border-right: 1px solid var(--rule);
    background: var(--ground);
  }

  h2 {
    padding: 0 0.5rem 0.875rem;
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.2;
  }

  .category {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.35rem 0.5rem 0.35rem 0.35rem;
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
      color var(--quick) var(--ease-out),
      box-shadow var(--quick) var(--ease-out);
  }

  .glyph {
    display: grid;
    place-items: center;
    flex: none;
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 7px;
    color: var(--pencil);
    transition:
      background-color var(--quick) var(--ease-out),
      color var(--quick) var(--ease-out);
  }

  .glyph svg {
    width: 18px;
    height: 18px;
  }

  .tag {
    margin-inline-start: auto;
    padding: 0.05rem 0.45rem;
    border-radius: 999px;
    background: var(--accent-wash);
    color: var(--accent);
    font-size: var(--step--2);
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

  .pane {
    overflow-y: auto;
    padding: 1.5rem 2rem 2rem;
  }

  .pane :global(.head) {
    /* Clear of the close button in the corner. */
    padding-inline-end: 2.5rem;
    margin-bottom: 1.5rem;
  }

  .pane :global(.head h3) {
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.25;
  }

  .pane :global(.lead) {
    margin-top: 0.25rem;
    color: var(--pencil);
  }

  .identity {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    margin-bottom: 1.25rem;
  }

  .identity h3 {
    font-family: var(--serif);
  }

  .identity .lead {
    margin-top: 0;
    font-size: var(--step--1);
  }

  .tagline {
    font-family: var(--serif);
    font-size: var(--step-1);
  }

  .blurb {
    margin: 0.35rem 0 1.5rem;
    color: var(--pencil);
  }

  /* A group: a quiet label, then its rows on one card. */
  .pane :global(.group + .group) {
    margin-top: 1.75rem;
  }

  .pane :global(.label) {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    min-height: 1.5rem;
    margin-bottom: 0.5rem;
    padding-inline: 0.125rem;
  }

  .pane :global(.label h4) {
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--ink-soft);
  }

  .status {
    font-size: var(--step--1);
    color: var(--pencil);
    animation: enter-fade var(--quick) ease;
  }

  .saved {
    color: var(--good);
  }

  .pane :global(.note) {
    margin-top: 0.5rem;
    padding-inline: 0.125rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .pane :global(.note.above) {
    margin: -0.25rem 0 0.625rem;
  }

  .pane :global(.card) {
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--raised);
  }

  .pane :global(.setting) {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.75rem 1.5rem;
    padding: 0.875rem 1rem;
  }

  .pane :global(.setting + .setting) {
    border-top: 1px solid var(--rule);
  }

  .setting.stacked {
    grid-template-columns: 1fr;
  }

  .pane :global(.title) {
    font-weight: 500;
  }

  .pane :global(.text p) {
    margin-top: 0.125rem;
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  .setting > select,
  .setting > input[type='text'] {
    width: 14rem;
  }

  .update-actions {
    display: flex;
    gap: 0.5rem;
  }

  .percent {
    font-size: var(--step--1);
    color: var(--pencil);
    font-variant-numeric: tabular-nums;
  }

  .progress {
    grid-column: 1 / -1;
    height: 0.375rem;
    border-radius: 999px;
    background: var(--rule);
    overflow: hidden;
  }

  .progress span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--accent);
    /* Ticks arrive once a second; the bar glides between them. */
    transition: width 1s linear;
  }

  @media (prefers-reduced-motion: reduce) {
    .progress span {
      transition: none;
    }
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
    gap: 0.5rem;
    padding: 0.625rem;
    border: 1px solid var(--rule);
    border-radius: 8px;
    background: var(--sheet);
    color: var(--ink-soft);
    font-size: var(--step--1);
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
    height: 3rem;
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

  .credits p:not(.note) {
    padding-inline: 0.125rem;
  }

  .pane :global(.foot) {
    display: grid;
    gap: 0.35rem;
    margin-top: 1.75rem;
    padding-inline: 0.125rem;
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  @media (max-width: 40rem) {
    dialog[open] {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
    }

    nav {
      flex-direction: row;
      flex-wrap: wrap;
      border-right: 0;
      border-bottom: 1px solid var(--rule);
    }

    h2 {
      flex-basis: 100%;
    }
  }

  /* A pane that comes into view fades in rather than replacing the last one in a blink. */
  .pane > * {
    animation: enter-fade var(--quick) ease;
  }
</style>
