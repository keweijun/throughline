<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { ImportMode, WaitingPackage } from '../lib/types';

  // A course package dropped on the library or chosen with Import course (ADR 0020): uploaded at once, so the learner
  // sees what it holds and chooses how to take it before anything is added to the library.
  let { file, onclose }: { file: File; onclose: () => void } = $props();

  let waiting = $state<WaitingPackage | null>(null);
  let mode = $state<ImportMode>('fresh');
  let name = $state('');
  let busy = $state(false);

  $effect(() => {
    const chosen = file;
    waiting = null;
    void (async () => {
      try {
        const view = await api.upload<WaitingPackage>('/api/library/packages', chosen);
        if (chosen !== file) return;
        waiting = view;
        mode = view.modes[0];
        name = view.name;
      } catch (error) {
        app.error = error instanceof Error ? error.message : String(error);
        onclose();
      }
    })();
  });

  const choices: Record<ImportMode, { label: string; detail: string }> = $derived({
    continue: { label: t('Continue where it was left'), detail: t('Progress, what the teacher remembers, notes and questions come too. Choose this for your own course from another computer, or a backup.') },
    fresh: { label: t('Start fresh'), detail: t('The route, lessons and exercises as written, without anyone’s answers or progress.') },
    'fresh-with-notes': { label: t('Start fresh, keep their notes and questions'), detail: t('As Start fresh, with their notes and questions to read beside yours. The teacher never sees them.') },
  });

  const level = $derived(
    waiting?.level === 'route' ? t('The route and its sources') : waiting?.level === 'lessons' ? t('The route, lessons and exercises') : t('The whole course'),
  );

  async function take() {
    if (!waiting) return;
    busy = true;
    try {
      const made = await api.post<{ name: string }>(`/api/library/packages/${waiting.token}`, { mode, name: name.trim() || null });
      await app.openCourse(made.name);
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
      busy = false;
    }
  }

  async function cancel() {
    if (waiting) api.delete(`/api/library/packages/${waiting.token}`).catch(() => {});
    onclose();
  }
</script>

<section class="import" aria-labelledby="import-title" aria-busy={!waiting}>
  {#if !waiting}
    <p class="muted">{t('Reading {file}…', { file: file.name })}</p>
  {:else}
    <h2 id="import-title">{t('Import {course}', { course: waiting.title })}</h2>
    <p class="facts">
      <span>{level}</span>
      <span>{t('Sources: {count}', { count: waiting.sources })}</span>
      {#if waiting.contents?.lessons}<span>{t('Lessons: {count}', { count: waiting.contents.lessons })}</span>{/if}
      {#if waiting.contents?.exercises}<span>{t('Exercises: {count}', { count: waiting.contents.exercises })}</span>{/if}
      {#if waiting.level === 'everything' && waiting.contents?.notes}<span>{t('Notes: {count}', { count: waiting.contents.notes })}</span>{/if}
      {#if waiting.level === 'everything' && waiting.contents?.questions}<span>{t('Questions: {count}', { count: waiting.contents.questions })}</span>{/if}
    </p>
    {#if waiting.built_for?.goal}<p class="current">{t('Built for: {goal}', { goal: waiting.built_for.goal })}</p>{/if}

    {#if waiting.modes.length > 1}
      <fieldset>
        <legend>{t('How to take it')}</legend>
        {#each waiting.modes as choice (choice)}
          <label class="choice">
            <input type="radio" name="import-mode" value={choice} bind:group={mode} />
            <span><strong>{choices[choice].label}</strong><span class="muted">{choices[choice].detail}</span></span>
          </label>
        {/each}
      </fieldset>
    {:else}
      <p class="muted">{t('You start fresh: the teacher writes what is not written yet, for you.')}</p>
    {/if}

    <label class="name">
      <span>{t('Course name')}</span>
      <input type="text" bind:value={name} spellcheck="false" pattern="[a-z0-9][a-z0-9\-]{'{0,63}'}" />
    </label>
    <div class="actions">
      <button class="btn btn-primary btn-small" disabled={busy || !name.trim()} onclick={take}>{busy ? t('Importing…') : t('Import')}</button>
      <button class="btn btn-small" disabled={busy} onclick={cancel}>{t('Cancel')}</button>
    </div>
  {/if}
</section>

<style>
  .import {
    margin: 0 0 1.4rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  h2 {
    margin: 0 0 0.3rem;
    font-size: 1.05rem;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1rem;
    margin: 0 0 0.4rem;
    color: var(--muted);
    font-size: 0.85rem;
  }

  .current {
    margin: 0 0 0.6rem;
  }

  fieldset {
    margin: 0.6rem 0;
    padding: 0;
    border: 0;
  }

  legend {
    margin-bottom: 0.35rem;
    font-weight: 600;
  }

  .choice {
    display: flex;
    gap: 0.55rem;
    align-items: baseline;
    padding: 0.3rem 0;
    cursor: pointer;
  }

  .choice > span {
    display: grid;
    gap: 0.1rem;
  }

  .name {
    display: flex;
    gap: 0.6rem;
    align-items: center;
    margin: 0.7rem 0;
  }

  .name input {
    width: 16rem;
    font-family: var(--mono, monospace);
  }

  .actions {
    display: flex;
    gap: 0.5rem;
  }
</style>
