<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import Preparation from './Preparation.svelte';
  import ChapterBuild from './ChapterBuild.svelte';

  let { conceptId }: { conceptId: string } = $props();

  let busy = $state(false);

  const route = $derived(app.state?.curriculum.route ?? []);
  const next = $derived(app.concept(route[route.indexOf(conceptId) + 1]));
  const pending = $derived(
    app.tasks(conceptId).filter((task) => !solved(task)).length,
  );
  const chapter = $derived(app.chapterOf(conceptId));
  const endsChapter = $derived(!!chapter && chapter.concept_ids.at(-1) === conceptId);
  const nextChapter = $derived(next ? app.chapterOf(next.id) : undefined);
  // The chapter after this one when it has no sections yet: the app (or Codex) builds it on request.
  const unbuilt = $derived.by(() => {
    const chapters = app.chapters;
    const later = chapters.slice(chapters.findIndex((c) => c.id === chapter?.id) + 1);
    return endsChapter && !next ? later.find((c) => !c.concept_ids.length) : undefined;
  });
  const activeSupplement = $derived((app.state?.questions ?? []).some((q) => q.choice === 'accept' && !q.returned));

  // Stays busy until the refreshed state shows the move, so a second click cannot repeat it.
  async function advance() {
    if (busy) return;
    busy = true;
    const moved = await app.act(() => api.post('/api/sections/next', { concept_id: conceptId, request_id: newId() }));
    busy = false;
    if (moved) window.scrollTo({ top: 0 });
  }
</script>

{#if endsChapter && chapter && app.hasLesson(conceptId)}
  <p class="chapter-end">
    <button class="link" onclick={() => app.viewChapter(chapter.id)}>{t("End of chapter: recap and quiz →")}</button>
  </p>
{/if}

{#if next}
  <section class="next" aria-label={t("Next section")}>
    <div>
      <p class="label">{nextChapter && nextChapter.id !== chapter?.id ? t("Next chapter: {chapter}", { chapter: nextChapter.title }) : t("Up next")}</p>
      <p class="title">{next.title}</p>
      {#if activeSupplement}
        <p class="note">{t("Finish or close the foundation supplement in Questions before moving on.")}</p>
      {:else if pending}
        <p class="note">
          {pending === 1 ? t('1 exercise stays open and will be waiting for you.') : t('{count} exercises stay open and will be waiting for you.', { count: pending })}
        </p>

      {/if}
      <Preparation />
    </div>
    <button class="btn btn-primary" disabled={busy || activeSupplement} onclick={advance}>{t("Enter next section")}</button>
  </section>
{:else if unbuilt}
  <section class="next done" aria-label={t("Next chapter")}>
    <div>
      <p class="title">{t("The next chapter, {chapter}, is not built yet.", { chapter: unbuilt.title })}</p>
      <ChapterBuild chapter={unbuilt} compact />
    </div>
  </section>
{:else if !next && app.hasLesson(conceptId)}
  <section class="next done" aria-label={t("End of route")}>
    <p class="title">{t("This is the last section on the route.")}</p>
  </section>
{/if}

<style>
  .next {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 3rem;
    padding: 1.25rem 1.35rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
  }

  .label {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .title {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .note {
    margin-top: 0.2rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .chapter-end {
    margin-top: 3rem;
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step-0);
    font-weight: 500;
    cursor: pointer;
  }

  .link:hover {
    text-decoration: underline;
  }

  .chapter-end + .next {
    margin-top: 1rem;
  }

  .done {
    background: transparent;
    border: 1px dashed var(--rule-strong);
  }
</style>
