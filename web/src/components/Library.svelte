<script lang="ts">
  import { t, locale, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { LibraryCourse } from '../lib/types';

  const templates: MessageKey[] = [
    '$guided-learning create a new course from these files: ',
    '$guided-learning add these files to the course {course}: ',
    '$guided-learning review the pages that still need review in the course {course}',
  ];

  let copied = $state<string | null>(null);
  let opening = $state<string | null>(null);

  const library = $derived(app.library);

  /** A new Codex chat in the Throughline project with the request typed in but not sent, so files can be attached. */
  function codexLink(key: MessageKey, course = '') {
    const prompt = t(key, { course });
    return `codex://new?prompt=${encodeURIComponent(prompt)}&path=${encodeURIComponent(library?.root ?? '')}`;
  }

  function updated(course: LibraryCourse) {
    if (!course.updated) return '';
    return new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(course.updated * 1000));
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copied = text;
      setTimeout(() => copied === text && (copied = null), 1800);
    } catch {
      copied = null;
    }
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
      <h1 id="library-title">{t('Your courses')}</h1>
      {#if library?.root}<p class="root">{t('Library folder')} <code>{library.root}</code></p>{/if}
    </div>
    <div class="header-actions">
      {#if library?.root}<a class="btn btn-primary btn-small" href={codexLink('$guided-learning create a new course from these files: ')}>{t('New course in Codex')}</a>{/if}
      {#if app.state}
        <button class="btn btn-small" onclick={() => (app.libraryOpen = false)}>{t('Back to {course}', { course: app.state.course.title })}</button>
      {/if}
    </div>
  </header>

  {#if !library}
    <p class="muted" aria-busy="true">{t('Loading your courses…')}</p>
  {:else if !library.courses.length}
    <div class="empty">
      <h2>{t('Create your first course')}</h2>
      <ol>
        <li>{t('Choose New course in Codex. A Codex chat opens in your Throughline project with the request typed in.')}</li>
        <li>{t('Attach your PDFs or notes, or name the folder they are in, and say in a sentence what you want to learn.')}</li>
        <li>{t('Send. Codex proposes a route, says what still needs checking, and opens the course here when it is done.')}</li>
      </ol>
      {#if library.root}<a class="btn btn-primary" href={codexLink('$guided-learning create a new course from these files: ')}>{t('New course in Codex')}</a>{/if}
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
              <span class="chip chip-caution">{t('{count} locations need review', { count: course.needs_review })}</span>
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
                <a href={codexLink('$guided-learning build the route for the course {course}', course.name)}>{t('Build the route in Codex')}</a>
              {/if}
              <a href={codexLink('$guided-learning add these files to the course {course}: ', course.name)}>{t('Add files in Codex')}</a>
              {#if course.needs_review}
                <a href={codexLink('$guided-learning review the pages that still need review in the course {course}', course.name)}>{t('Review in Codex')}</a>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  <aside class="codex" aria-labelledby="codex-title">
    <h2 id="codex-title">{t('Courses are built in Codex')}</h2>
    <p class="muted">{t('The Codex buttons open a new chat in your Throughline project with the request typed in. Attach your files, send, and this page updates when Codex is done.')}</p>
    <p class="muted">{t('Using the Codex CLI, or nothing opened? Copy a request into Codex in your Throughline folder instead:')}</p>
    <ul class="prompts">
      {#each templates as key (key)}
        {@const prompt = t(key, { course: 'my-course' }).trim()}
        <li>
          <code>{prompt}</code>
          <button class="btn btn-quiet btn-small" onclick={() => copy(prompt)}>{copied === prompt ? t('Copied') : t('Copy')}</button>
        </li>
      {/each}
    </ul>
  </aside>
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

  .courses > li {
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

  .codex {
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
  }

  .codex h2 {
    font-size: var(--step-0);
    font-family: var(--sans);
  }

  .prompts {
    display: grid;
    gap: 0.5rem;
    margin-top: 0.75rem;
    padding: 0;
    list-style: none;
  }

  .prompts li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.5rem 0.5rem 0.5rem 0.85rem;
    border-radius: var(--radius);
    background: var(--raised);
    border: 1px solid var(--rule);
  }

  .prompts code {
    font-family: var(--mono);
    font-size: var(--step--1);
    overflow-wrap: anywhere;
  }
</style>
