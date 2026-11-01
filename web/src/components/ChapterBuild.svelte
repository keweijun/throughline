<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Chapter } from '../lib/types';
  import CodexLink from './CodexLink.svelte';

  /** Building an outlined chapter: in the app, in the background; Codex is the fallback when that fails. */
  let { chapter, compact = false }: { chapter: Chapter; compact?: boolean } = $props();

  let busy = $state(false);

  const build = $derived(app.buildOf(chapter.id));
  const status = $derived(build?.status === 'done' ? undefined : build?.status);
  const other = $derived.by(() => {
    const active = app.activeBuild;
    return active && active.chapter_id !== chapter.id ? app.chapters.find((c) => c.id === active.chapter_id) : undefined;
  });
  const course = $derived(app.libraryCourse);

  async function start() {
    if (busy) return;
    busy = true;
    await app.buildChapter(chapter.id);
    busy = false;
  }
</script>

<div class="build" class:compact>
  {#if status === 'queued' || status === 'building'}
    <p class="progress" role="status">
      <span class="live-dot" aria-hidden="true"></span>
      <span>
        {status === 'queued'
          ? t("Building starts as soon as your current lesson or answer finishes.")
          : t("Building this chapter from your files…")}
      </span>
    </p>
    {#if !compact}
      <p class="note">{t("Keep studying meanwhile. This page updates by itself when the chapter is ready.")}</p>
    {/if}
  {:else}
    {#if status === 'failed' || status === 'interrupted'}
      <div class="problem" role="alert">
        <p>{status === 'failed' ? t("Building this chapter failed.") : t("Building this chapter was interrupted when Throughline stopped.")}</p>
        {#if status === 'failed' && build?.error}<p class="error">{build.error}</p>{/if}
      </div>
    {/if}
    <div class="actions">
      <button class="btn btn-primary" class:btn-small={compact} disabled={busy || !!other} onclick={start}>
        {status ? t("Try building again") : t("Build this chapter")}
      </button>
      {#if (status === 'failed' || status === 'interrupted') && course}
        <CodexLink prompt={t('$throughline build the chapter "{chapter}" of the course {course}', { chapter: chapter.title, course: course.name })} origin={{ label: t('Chapter: {chapter}', { chapter: chapter.title }), text: `chapter "${chapter.title}" (${chapter.id})` }}>
          {t("Build this chapter in Studio")}
        </CodexLink>
      {/if}
    </div>
    {#if other}
      <p class="note">{t("The chapter {chapter} is being built first; build this one when it is ready.", { chapter: other.title })}</p>
    {:else if !compact && !status}
      <p class="note">{t("Throughline builds it from your files in the background, and you can keep studying earlier chapters meanwhile.")}</p>
    {/if}
  {/if}
</div>

<style>
  .build {
    display: grid;
    justify-items: start;
    gap: 0.6rem;
  }

  .compact {
    gap: 0.4rem;
    margin-top: 0.4rem;
  }

  .progress {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: var(--step-0);
    color: var(--accent);
  }

  .compact .progress {
    font-size: var(--step--1);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
  }

  .actions :global(a) {
    font-size: var(--step--1);
  }

  .problem {
    display: grid;
    gap: 0.25rem;
    font-size: var(--step-0);
  }

  .error {
    font-family: var(--mono);
    font-size: var(--step--1);
    color: var(--danger);
    overflow-wrap: anywhere;
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
