<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Chapter } from '../lib/types';

  // The route folded to a capsule: a numbered badge per chapter, and the sections of the chapter in view as dots in a
  // tray under its badge. Its markers are the full route's own (.route-badge, .route-dot), so folding only hides labels.
  let box = $state<HTMLElement>();

  const route = $derived(app.state?.curriculum.route ?? []);
  const currentIndex = $derived(app.routeIndex(app.currentId));
  // A course always has a chapter once it has a route (ADR 0006); the fallback keeps an unchaptered state drawable.
  const chapters = $derived<Chapter[]>(app.chapters.length ? app.chapters : [{ id: '', title: '', concept_ids: route }]);
  // The chapters open in the full route open here too, so folding and unfolding never changes what shows.
  const isOpen = (chapter: Chapter) => !app.chapters.length || app.chapterOpen(chapter.id);
  const currentChapter = $derived(app.chapterOf(app.currentId)?.id);
  // The section looked at away from the current one, if any.
  const viewing = $derived(app.viewingChapter || app.reviewOpen || app.viewingId === app.currentId ? null : app.viewingId);

  const name = (chapter: Chapter, index: number) => t('Chapter {number}', { number: index + 1 }) + ' · ' + chapter.title;
  const studiedIn = (ids: string[]) => ids.filter((id) => app.studied(id)).length;
  const progress = (chapter: Chapter) =>
    chapter.concept_ids.length
      ? t('{studied}/{total} sections studied', { studied: studiedIn(chapter.concept_ids), total: chapter.concept_ids.length })
      : t('Not built yet');

  const labels: Record<'current' | 'visited' | 'upcoming', MessageKey> = { current: 'Current section', visited: 'Visited', upcoming: 'Not started' };
  function stateOf(id: string) {
    if (id === app.currentId) return 'current';
    return route.indexOf(id) < currentIndex || app.hasLesson(id) ? 'visited' : 'upcoming';
  }

  // A long chapter shows nine sections around the one in view, and counts the rest.
  const WINDOW = 9;
  function windowed(ids: string[]) {
    if (ids.length <= WINDOW) return { ids, before: 0, after: 0 };
    const focus = [viewing, app.currentId].map((id) => ids.indexOf(id ?? '')).find((i) => i >= 0) ?? ids.findIndex((id) => !app.studied(id));
    const start = Math.min(Math.max(0, focus - Math.floor(WINDOW / 2)), ids.length - WINDOW);
    return { ids: ids.slice(start, start + WINDOW), before: start, after: ids.length - start - WINDOW };
  }

  // Keep what the learner is looking at in view when the capsule scrolls: the section looked at, else the current one,
  // else the chapter in view, else the chapter being studied.
  $effect(() => {
    void [app.viewingId, app.viewingChapter, app.currentId, app.chapterInView];
    requestAnimationFrame(() => {
      if (!box || box.scrollHeight <= box.clientHeight) return;
      const item = ['.route-dot.viewing', '.route-dot.current', '.route-badge.open', '.route-badge.here']
        .map((selector) => box!.querySelector<HTMLElement>(selector))
        .find(Boolean);
      if (!item) return;
      const top = item.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
      if (top < box.scrollTop || top + item.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = top - box.clientHeight / 3;
    });
  });
</script>

<div class="mini" bind:this={box}>
  <!-- Unfolding needs room beside the reading column; without it the full route opens on hover instead. -->
  {#if !app.stageNarrow}
    <button class="unfold" aria-label={t('Unfold the route')} title={t('Unfold the route (r)')} onclick={() => app.toggleRoute()}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
  {/if}
  <ol class="chapters">
    {#each chapters as chapter, index (chapter.id)}
      {@const total = chapter.concept_ids.length}
      {@const done = studiedIn(chapter.concept_ids)}
      {@const open = isOpen(chapter)}
      <li class="chapter">
        {#if chapters.length > 1}
          <button
            class="route-badge"
            class:open={open && total > 0}
            class:here={chapter.id === currentChapter}
            class:unbuilt={!total}
            class:done={total > 0 && done === total}
            style:--progress="{total ? (done / total) * 360 : 0}deg"
            aria-label={name(chapter, index) + ', ' + progress(chapter)}
            title={name(chapter, index) + ' · ' + progress(chapter)}
            onclick={() => app.viewChapter(chapter.id)}
          ><span aria-hidden="true">{index + 1}</span></button>
        {/if}
        {#if open && total}
          {@const shown = windowed(chapter.concept_ids)}
          <ol class="tray">
            {#if shown.before}<li class="more" aria-hidden="true">+{shown.before}</li>{/if}
            {#each shown.ids as id (id)}
              {@const status = stateOf(id)}
              <li class:passed={route.indexOf(id) < currentIndex}>
                <button
                  class="dot"
                  aria-label={(app.concept(id)?.title ?? id) + ', ' + t(labels[status])}
                  title={app.concept(id)?.title ?? id}
                  onclick={() => app.view(id)}
                ><span class="route-dot {status}" class:viewing={id === viewing} class:skipped={app.isSkipped(id)}></span></button>
              </li>
            {/each}
            {#if shown.after}<li class="more" aria-hidden="true">+{shown.after}</li>{/if}
          </ol>
        {/if}
      </li>
    {/each}
  </ol>
</div>

<style>
  /* The capsule: centred in the column by auto margins while it fits, scrolling inside itself when it does not. */
  .mini {
    --marker-ground: var(--sheet);
    display: flex;
    flex-direction: column;
    align-items: center;
    width: var(--capsule);
    max-height: calc(100% - 2rem);
    margin: auto;
    padding: 0.5rem 0 0.7rem;
    overflow-y: auto;
    scrollbar-width: none;
    border: 1px solid var(--rule);
    border-radius: 999px;
    background: var(--sheet);
    box-shadow: 0 1px 3px var(--shadow-near);
    pointer-events: auto;
    animation: capsule-in var(--settle) var(--ease-out);
    transition:
      border-color var(--quick) ease,
      box-shadow var(--quick) ease;
  }

  .mini:hover {
    border-color: var(--rule-strong);
    box-shadow: 0 2px 8px var(--shadow-far);
  }

  @keyframes capsule-in {
    from {
      opacity: 0;
      transform: translateX(-0.4rem);
    }
  }

  /* The capsule's own controls; the chapter badges keep the shared .route-badge look. */
  .unfold,
  .dot {
    position: relative;
    display: block;
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
  }

  .unfold {
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    margin-bottom: 0.4rem;
    border-radius: 50%;
    color: var(--pencil);
    transition:
      color var(--quick) ease,
      background-color var(--quick) ease;
  }

  .unfold:hover {
    background: var(--accent-wash);
    color: var(--accent);
  }

  .chapters,
  .tray {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .chapter {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .chapter + .chapter::before {
    content: '';
    width: 2px;
    height: 0.5rem;
    background: var(--rule);
  }

  /* The chapter in view hangs its sections below its badge, on a track filled up to where the learner is. */
  .tray {
    width: 1.75rem;
    margin: 0.3rem 0 0.1rem;
    padding: 0.3rem 0;
    border-radius: 999px;
    background: var(--accent-wash);
    animation: tray-in var(--settle) var(--ease-out);
  }

  @keyframes tray-in {
    from {
      opacity: 0;
      transform: scaleY(0.85);
      transform-origin: top;
    }
  }

  .tray li {
    position: relative;
  }

  .tray li:not(:last-child)::after {
    content: '';
    position: absolute;
    top: 50%;
    left: calc(50% - 1px);
    width: 2px;
    height: 100%;
    background: var(--rule-strong);
  }

  .tray li.passed:not(:last-child)::after {
    background: var(--accent);
  }

  .dot {
    z-index: 1;
    display: grid;
    place-items: center;
    width: 1.75rem;
    height: 1.35rem;
  }

  .more {
    font-size: 0.65rem;
    line-height: 1.2rem;
    color: var(--pencil);
    font-variant-numeric: tabular-nums;
  }

  @media (prefers-reduced-motion: reduce) {
    .mini,
    .tray {
      animation: none;
    }
  }
</style>
