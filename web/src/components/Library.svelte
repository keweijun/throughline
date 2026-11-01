<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { api } from '../lib/api';
  import { t, locale } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { CodexCheck, CodexChecks, LauncherStatus, LibraryCourse } from '../lib/types';
  import CodexLink from './CodexLink.svelte';
  import LauncherHelp from './LauncherHelp.svelte';

  let opening = $state<string | null>(null);
  let launcher = $state<LauncherStatus | null>(null);
  let checks = $state<CodexCheck[]>([]);
  let checking = $state(false);

  const failing = $derived(checks.filter((check) => !check.ok));

  let poll: ReturnType<typeof setTimeout> | undefined;

  // Neither is needed to use the library, so a failure to load them shows nothing. Whether Codex answers is probed once
  // per host in the background; while it runs `checking` is true and this asks again shortly.
  async function loadChecks(again = false) {
    clearTimeout(poll);
    try {
      const view = again ? await api.post<CodexChecks>('/api/checks') : await api.get<CodexChecks>('/api/checks');
      checks = view.checks;
      checking = view.checking;
    } catch {
      checks = [];
      checking = false;
    }
    if (checking) poll = setTimeout(() => void loadChecks(), 1500);
  }

  onMount(() => {
    void loadChecks();
    api.get<LauncherStatus>('/api/launcher').then((status) => (launcher = status), () => {});
  });
  onDestroy(() => clearTimeout(poll));

  async function dismissLauncher() {
    if (launcher) launcher = { ...launcher, dismissed: true };
    try {
      await api.post('/api/seen', { id: 'launcher' });
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    }
  }

  /** What failed and what to do about it; a check this version does not know is shown as the host words it. */
  function problem(check: CodexCheck) {
    if (check.id === 'codex') return [t('Codex was not found.'), t('Install Codex (the desktop app or the CLI) and sign in; lessons need it.')];
    if (check.id === 'answers') return [t('Codex could not answer:'), `${check.detail.replace(/\.$/, '')}. ${t('Check that “codex” works in a terminal (signed in, or with an API key).')}`];
    return [check.label, check.fix];
  }

  const library = $derived(app.library);
  const newCourse = $derived(t('$throughline create a new course from these files: '));

  function updated(course: LibraryCourse) {
    if (!course.updated) return '';
    return new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(course.updated * 1000));
  }

  async function open(course: LibraryCourse) {
    opening = course.name;
    await app.openCourse(course.name);
    opening = null;
  }
</script>

<section class="library" aria-labelledby="library-title">
  <header>
    <div>
      <h1 id="library-title">{t('All courses')}</h1>
      {#if library?.root}<p class="root">{t('Library folder')} <code>{library.root}</code></p>{/if}
    </div>
    <div class="header-actions">
      <CodexLink class="btn btn-primary btn-small" prompt={newCourse}>{t('New course in Codex')}</CodexLink>
      {#if app.state}
        <button class="btn btn-small" onclick={() => (app.libraryOpen = false)}>{t('Back to {course}', { course: app.state.course.title })}</button>
      {/if}
    </div>
  </header>

  {#if failing.length}
    <div class="checks" role="alert">
      <ul>
        {#each failing as check (check.id)}
          {@const [what, fix] = problem(check)}
          <li><strong>{what}</strong> {fix}</li>
        {/each}
      </ul>
      <button class="btn btn-small" disabled={checking} onclick={() => loadChecks(true)}>{checking ? t('Checking…') : t('Check again')}</button>
    </div>
  {/if}

  {#if launcher && !launcher.dismissed}
    <aside class="next-time" aria-labelledby="next-time-title">
      <div class="next-time-head">
        <h2 id="next-time-title">{t('Opening Throughline next time')}</h2>
        <button class="btn btn-quiet btn-small" onclick={dismissLauncher}>{t('Dismiss')}</button>
      </div>
      <LauncherHelp {launcher} />
      <p class="muted later">{t('You can find this again in Settings → About.')}</p>
    </aside>
  {/if}

  {#if !library}
    <p class="muted" aria-busy="true">{t('Loading your courses…')}</p>
  {:else if !library.courses.length}
    <div class="empty">
      <h2>{t('Create your first course')}</h2>
      <ol>
        <li>{t('Choose New course in Codex, or start any Codex chat with $throughline. A chat opens with the request typed in.')}</li>
        <li>{t('Attach your PDFs or notes, or name the folder they are in, and say in a sentence what you want to learn.')}</li>
        <li>{t('Send. Codex asks a few questions about your goal and background, each with a recommended answer, proposes a route, and opens the course here when it is done.')}</li>
      </ol>
      <CodexLink class="btn btn-primary" prompt={newCourse}>{t('New course in Codex')}</CodexLink>
    </div>
  {:else}
    <ul class="courses">
      {#each library.courses as course (course.path)}
        {@const active = course.path === library.active}
        <li class:active>
          <div class="summary">
            <h2>{course.title ?? course.name}</h2>
            {#if course.error}
              <p class="problem">{t('This course could not be read: {error}', { error: course.error })}</p>
            {:else}
              <p class="facts">
                <span>{course.name}</span>
                <span>{t('Sources: {count}', { count: course.sources ?? 0 })}</span>
                <span>{t('Sections: {count}', { count: course.concepts ?? 0 })}</span>
                {#if updated(course)}<span>{t('Updated {date}', { date: updated(course) })}</span>{/if}
              </p>
              {#if course.goal}<p class="current">{t('Goal: {goal}', { goal: course.goal })}</p>{/if}
              {#if course.current}<p class="current">{t('Now studying: {section}', { section: course.current })}</p>{/if}
            {/if}
          </div>
          <div class="state">
            {#if course.needs_review}
              <span class="chip chip-caution">{t('{count} source locations not checked yet', { count: course.needs_review })}</span>
            {/if}
            {#if active}
              <button class="btn btn-small" onclick={() => (app.libraryOpen = false)}>{t('Continue')}</button>
            {:else if !course.error && course.concepts}
              <button class="btn btn-primary btn-small" disabled={opening !== null} onclick={() => open(course)}>
                {opening === course.name ? t('Opening…') : t('Open')}
              </button>
            {:else if !course.error}
              <span class="chip chip-plain">{t('Route not built yet')}</span>
            {/if}
          </div>
          {#if !course.error && library.root}
            <div class="codex-actions">
              {#if !course.concepts}
                <CodexLink prompt={t('$throughline build the route for the course {course}', { course: course.name })}>{t('Build the route in Codex')}</CodexLink>
              {/if}
              <CodexLink prompt={t('$throughline add these files to the course {course}: ', { course: course.name })}>{t('Add files in Codex')}</CodexLink>
              {#if course.needs_review}
                <CodexLink prompt={t('$throughline review the pages that still need review in the course {course}', { course: course.name })}>{t('Check sources in Codex')}</CodexLink>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  <!-- Without a library folder there are no Codex buttons for this to explain. -->
  {#if library?.root}
  <aside class="codex" aria-labelledby="codex-title">
    <h2 id="codex-title">{t('Courses are built in Codex')}</h2>
    <p class="muted">{t('The Codex buttons open a new Codex chat with a $throughline request typed in. Attach your files, send, and this page updates when Codex is done.')}</p>
    <p class="muted">{t('Each Codex button also copies its request. Using the Codex CLI, or nothing opened? Paste it into Codex started in your Throughline folder.')}</p>
  </aside>
  {/if}
</section>

<style>
  .library {
    grid-column: 1 / -1;
    width: 100%;
    max-width: 52rem;
    margin-inline: auto;
    padding: 2.5rem clamp(1rem, 4vw, 3rem) 6rem;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: var(--step-3);
    font-weight: 600;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
  }

  .root,
  .muted,
  .facts {
    color: var(--pencil);
    font-size: var(--step--1);
    overflow-wrap: anywhere;
  }

  .courses {
    display: grid;
    gap: 0.75rem;
    padding: 0;
    list-style: none;
  }

  .courses > li:nth-child(2) {
    animation-delay: 40ms;
  }

  .courses > li:nth-child(3) {
    animation-delay: 80ms;
  }

  .courses > li:nth-child(n + 4) {
    animation-delay: 120ms;
  }

  .courses > li {
    animation: enter-rise var(--settle) var(--ease-out) backwards;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
    padding: 1rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
  }

  .courses > li.active {
    border-color: var(--accent);
    box-shadow: inset 3px 0 0 var(--accent);
  }

  .summary {
    min-width: 0;
    flex: 1 1 18rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem 0.9rem;
    margin-top: 0.2rem;
  }

  .current {
    margin-top: 0.35rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .problem {
    color: var(--danger);
    font-size: var(--step--1);
  }

  .codex-actions {
    flex-basis: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 1.1rem;
    padding-top: 0.6rem;
    border-top: 1px solid var(--rule);
    font-size: var(--step--1);
  }

  .state {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
  }

  .empty {
    display: grid;
    justify-items: start;
    gap: 0.9rem;
    padding: 1.5rem 1.5rem 1.75rem;
    border: 1px dashed var(--rule-strong);
    border-radius: 10px;
  }

  .empty ol {
    display: grid;
    gap: 0.45rem;
    padding-left: 1.25rem;
    color: var(--ink-soft);
  }

  .checks {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem 1.5rem;
    margin-bottom: 1rem;
    padding: 0.85rem 1.25rem;
    border: 1px solid var(--caution);
    border-radius: 10px;
    background: var(--caution-wash);
  }

  .checks ul {
    display: grid;
    gap: 0.3rem;
    flex: 1 1 24rem;
    padding: 0;
    list-style: none;
    font-size: var(--step--1);
  }

  .checks strong {
    color: var(--caution);
    font-weight: 600;
  }

  .next-time {
    margin-bottom: 1rem;
    padding: 1rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: inset 3px 0 0 var(--accent-wash);
  }

  .next-time-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.35rem;
  }

  .next-time h2 {
    font-size: var(--step-0);
    font-family: var(--sans);
  }

  .later {
    margin-top: 0.6rem;
  }

  .codex {
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
  }

  .codex h2 {
    font-size: var(--step-0);
    font-family: var(--sans);
  }
</style>
