<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { PackageContents, ShareLevel } from '../lib/types';

  // Sharing or backing up the course as one course package (ADR 0020). The learner picks how much it holds; the counts
  // say what each level shares before anything is written.
  let { active }: { active: boolean } = $props();

  let levels = $state<Record<ShareLevel, PackageContents> | null>(null);
  let name = $state('');
  let level = $state<ShareLevel>('lessons');

  $effect(() => {
    if (!active) return;
    api.get<{ name: string; levels: Record<ShareLevel, PackageContents> }>('/api/course/package').then(
      (view) => {
        levels = view.levels;
        name = view.name;
      },
      (error) => (app.error = error instanceof Error ? error.message : String(error)),
    );
  });

  const options: { id: ShareLevel; label: () => string; detail: () => string }[] = [
    { id: 'route', label: () => t('The route'), detail: () => t('Chapters, sections and sources as read. Their teacher writes every lesson and exercise for them.') },
    { id: 'lessons', label: () => t('The route, lessons and exercises'), detail: () => t('Also the lessons and exercises written so far, without your answers or progress.') },
    { id: 'everything', label: () => t('Everything'), detail: () => t('The whole course, for a backup or your other computer. Whoever imports it can still start fresh.') },
  ];

  /** What Everything adds of the learner's own: shown before they share it, since notes are otherwise private. */
  const own = $derived.by(() => {
    const all = levels?.everything;
    if (!all) return '';
    const parts = [
      all.notes && t('Notes: {count}', { count: all.notes }),
      all.questions && t('Questions: {count}', { count: all.questions }),
      all.evidence && t('your answers and progress'),
      t('what the teacher remembers about you'),
    ].filter(Boolean);
    return parts.join(' · ');
  });
</script>

<p class="lead">{t('Share this course as one file, or keep a copy. Whoever imports it gets a course of their own; nothing syncs back.')}</p>
<fieldset class="levels" aria-busy={!levels} aria-label={t('How much to share')}>
  {#each options as option (option.id)}
    {@const counts = levels?.[option.id]}
    <label class="choice">
      <input type="radio" name="share-level" value={option.id} bind:group={level} />
      <span>
        <strong>{option.label()}</strong>
        <span class="muted">{option.detail()}</span>
        {#if counts && option.id === 'lessons'}
          <span class="counts">{t('Lessons: {count}', { count: counts.lessons })} · {t('Exercises: {count}', { count: counts.exercises })}</span>
        {:else if option.id === 'everything' && own}
          <span class="counts">{t('Also shares: {what}', { what: own })}</span>
        {/if}
      </span>
    </label>
  {/each}
</fieldset>
<p class="note">{t('The file holds the course’s source documents. Share it only with people allowed to have them.')}</p>
<div class="actions">
  <a class="btn btn-primary btn-small" class:disabled={!levels} href="/api/course/package/{level}" download="{name}.throughline">{t('Download the file')}</a>
</div>

<style>
  .lead,
  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .levels {
    margin: 0;
    padding: 0;
    border: 0;
    display: grid;
    gap: 0.5rem;
  }

  .choice {
    display: flex;
    gap: 0.55rem;
    align-items: baseline;
    cursor: pointer;
  }

  .choice > span {
    display: grid;
    gap: 0.1rem;
  }

  .counts {
    font-size: 0.85rem;
  }

  .actions {
    display: flex;
    gap: 0.4rem;
  }

  .disabled {
    pointer-events: none;
    opacity: 0.5;
  }
</style>
