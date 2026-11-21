<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { Chapter } from '../lib/types';
  import KeyPoints from './KeyPoints.svelte';
  import Lesson from './Lesson.svelte';
  import StudioHandoff from './StudioHandoff.svelte';

  /**
   * A chapter's key points sheet (ADR 0024): a paragraph on how its sections connect, then each studied section's
   * points in route order. It replaces the chapter recap; recaps written before stay readable, folded, below it.
   */
  let { chapter }: { chapter: Chapter } = $props();

  const sections = $derived(chapter.concept_ids.map((id) => app.keyPoints(id)).filter((v) => !!v));
  // Sections studied before key points get theirs in the background, a section at a time.
  const waiting = $derived(chapter.concept_ids.filter((id) => !app.keyPoints(id) && app.studied(id)).length);
  const sheet = $derived(app.chapterSheet(chapter.id));
  const recaps = $derived(app.recaps(chapter.id).filter((r) => r.status === 'completed'));
</script>

<section class="sheet" aria-labelledby="sheet-title">
  <!-- What Studio can make from the chapter sits by the heading of what it would sum up (issue #229). -->
  <header>
    <h2 id="sheet-title">{t("Key points")}</h2>
    {#if sections.length}
      <StudioHandoff
        variant="link"
        place={{ kind: 'chapter', chapter: chapter.id }}
        label={t("One-page summary in Studio")}
        request={t('Make me a one-page summary of the chapter "{chapter}": its key results with when they hold, how they connect, and the mistakes to avoid.', { chapter: chapter.title })}
        context={{ label: t('Chapter: {chapter}', { chapter: chapter.title }), text: `chapter "${chapter.title}" (${chapter.id})` }}
      />
    {/if}
  </header>
  {#if sheet}
    <div class="prose connection" use:markdown={{ language: locale.language, text: sheet.connection }}></div>
  {/if}
  {#each sections as value (value.concept_id)}
    <KeyPoints {value} section />
  {/each}
  {#if waiting}
    <p class="note">
      {waiting === 1 ? t("The key points of 1 studied section are still being written.") : t("The key points of {count} studied sections are still being written.", { count: waiting })}
    </p>
  {/if}
  {#if recaps.length}
    <details class="recaps">
      <summary>{recaps.length === 1 ? t("Earlier chapter recap") : t("Earlier chapter recaps ({count})", { count: recaps.length })}</summary>
      <div class="lessons">
        {#each recaps as turn (turn.id)}
          <Lesson {turn} />
        {/each}
      </div>
    </details>
  {/if}
</section>

<style>
  .sheet {
    display: grid;
    gap: 1.4rem;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.4rem 1rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .connection {
    margin-top: -0.6rem;
    font-size: var(--step-0);
    line-height: 1.6;
    color: var(--ink-soft);
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .recaps summary {
    font-size: var(--step--1);
    color: var(--pencil);
    cursor: pointer;
  }

  .lessons {
    display: grid;
    gap: 2.5rem;
    margin-top: 1rem;
  }
</style>
