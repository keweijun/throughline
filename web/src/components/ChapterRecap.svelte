<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Chapter } from '../lib/types';
  import Lesson from './Lesson.svelte';

  let { chapter }: { chapter: Chapter } = $props();

  // A recap belongs to the chapter: starting one never moves the learner, but it waits for a lesson being written.
  let busy = $state(false);
  const recaps = $derived(app.recaps(chapter.id));
  const running = $derived(app.runningLesson);
  const finished = $derived(recaps.at(-1)?.status === 'completed');

  async function start() {
    if (busy || running) return;
    busy = true;
    await app.recapChapter(chapter.id);
    busy = false;
  }
</script>

<section class="recap" aria-labelledby="recap-title">
  <h2 id="recap-title">{t("Chapter recap")}</h2>
  <p class="note">{t("A recap connects the chapter's sections and lists exercises you set aside. No new material.")}</p>

  {#if recaps.length}
    <div class="lessons">
      {#each recaps as turn (turn.id)}
        <Lesson {turn} />
      {/each}
    </div>
  {/if}

  {#if !running || running.chapter_id !== chapter.id}
    <div class="row">
      <button class="btn" class:btn-primary={!recaps.length} disabled={busy || !!running} onclick={start}>
        {recaps.length ? t("Recap again") : t("Recap this chapter")}
      </button>
      {#if running}<span class="hint">{t("Another lesson is being written. Pause it first.")}</span>{/if}
    </div>
  {/if}
  {#if finished}<p class="offer">{t("Ready to check yourself? Take the chapter quiz below.")}</p>{/if}
</section>

<style>
  .recap {
    display: grid;
    gap: 0.9rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .note {
    margin-top: -0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .lessons {
    display: grid;
    gap: 2.5rem;
    margin-block: 0.5rem 0.75rem;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .hint {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .offer {
    font-size: var(--step-0);
    color: var(--ink-soft);
  }
</style>
