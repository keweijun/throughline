<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';
  import StudioHandoff from './StudioHandoff.svelte';

  /**
   * Once per learner, in the first course they open (issue #229): what Studio is, three things it could do for this
   * course, each one click away, and why full access makes that smoother. Most learners take the app for a chat tutor;
   * this is the moment to show it is Codex working on their course.
   */
  const KEY = 'studio-intro';
  const shown = $derived(!!app.seen && !app.seen.includes(KEY) && !!app.state?.curriculum.route.length);
  const chapter = $derived(app.chapters[0]);
  const source = $derived(app.state?.sources.find((s) => s.status !== 'failed'));
  const sourceName = $derived(source?.path.split(/[\\/]/).pop() ?? '');
  const context = { label: t('Getting started'), text: 'the introduction to Studio shown in the first course' };
  const examples = $derived([
    ...(chapter ? [{ key: 'sheet', label: t('Make a formula sheet for "{chapter}"', { chapter: chapter.title }),
                     request: t('Make me a one-page formula sheet for the chapter "{chapter}": each result with when it holds.', { chapter: chapter.title }) }] : []),
    ...(source ? [{ key: 'exercises', label: t('Find the problems in {source} and add them as exercises', { source: sourceName }),
                    request: t('Find the problems and exercises in {source} and add them as exercises to the sections they practise.', { source: sourceName }) }] : []),
    ...(chapter ? [{ key: 'mock', label: t('Write a mock exam on "{chapter}"', { chapter: chapter.title }),
                     request: t('Write me a mock exam on the chapter "{chapter}", built from the course\'s own exercises and any past papers among its sources.', { chapter: chapter.title }) }] : []),
  ]);
  let switching = $state(false);

  $effect(() => {
    if (shown && studio.access === null) void studio.loadAccess();
  });

  async function fullAccess() {
    switching = true;
    try {
      await studio.setFullAccess(true);
    } finally {
      switching = false;
    }
  }
</script>

{#if shown}
  <aside class="intro" aria-labelledby="studio-intro-title">
    <header>
      <h2 id="studio-intro-title">{t("Codex works on this course with you")}</h2>
      <button class="btn btn-quiet btn-small close" onclick={() => app.markSeen(KEY)} aria-label={t("Close")} title={t("Close")}>
        <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg>
      </button>
    </header>
    <p>{t("Lessons, questions and reviews here are quick. Anything bigger goes to Studio, where Codex works on the course itself: it reads your files, writes sheets and mock exams, adds problem sets as exercises and rebuilds sections. Try one:")}</p>
    <ul>
      {#each examples as item (item.key)}
        <li><StudioHandoff variant="link" place={{ kind: 'intro', example: item.key }} label={item.label} request={item.request} {context} /></li>
      {/each}
    </ul>
    {#if studio.access && !studio.access.full_access}
      <div class="access">
        <p>{t("Studio asks before each request. With full access it simply starts, and Codex can change files in this course's folder without asking.")}</p>
        <button class="btn btn-small" disabled={switching} onclick={fullAccess}>{t("Use full access")}</button>
      </div>
    {/if}
  </aside>
{/if}

<style>
  .intro {
    display: grid;
    gap: 0.75rem;
    margin-bottom: 2rem;
    padding: 1rem 1.2rem;
    border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--rule));
    border-radius: var(--radius);
    background: var(--accent-wash);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .close {
    margin: -0.3rem -0.4rem -0.3rem 0;
    padding: 0.25rem;
    color: var(--pencil);
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  p {
    margin: 0;
    font-size: var(--step-0);
    line-height: 1.5;
  }

  ul {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* The note and its button on one line, set off from the examples above. */
  .access {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1.25rem;
    padding-top: 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--accent) 25%, var(--rule));
  }

  .access p {
    flex: 1 1 20rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }
</style>
