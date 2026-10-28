<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { Chapter } from '../lib/types';

  // The route folded beside a narrow stage. Two designs are on trial: a progress track of fixed height whatever the
  // course's length, and a chapter stepper that opens only the chapter in view. Both open the full route on hover.
  let { variant }: { variant: 'track' | 'stepper' } = $props();

  let box = $state<HTMLElement>();

  const route = $derived(app.state?.curriculum.route ?? []);
  const currentIndex = $derived(app.routeIndex(app.currentId));
  // A course always has a chapter once it has a route (ADR 0006); the fallback keeps an unchaptered state drawable.
  const chapters = $derived<Chapter[]>(app.chapters.length ? app.chapters : [{ id: '', title: '', concept_ids: route }]);
  const currentChapter = $derived(app.chapterOf(app.currentId)?.id);
  // The section looked at away from the current one, if any.
  const viewing = $derived(app.viewingChapter || app.reviewOpen || app.viewingId === app.currentId ? null : app.viewingId);
  // The stepper opens the chapter being looked at, else the one being studied.
  const openChapter = $derived(app.viewingChapter ?? app.chapterOf(app.viewingId)?.id ?? currentChapter);

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

  // Keep where the learner is in view when the folded route scrolls.
  $effect(() => {
    void app.viewingId;
    void app.currentId;
    requestAnimationFrame(() => {
      const item = box?.querySelector<HTMLElement>('.marker, .dot.current, .ring.here');
      if (!box || !item || box.scrollHeight <= box.clientHeight) return;
      const top = item.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
      if (top < box.scrollTop || top > box.scrollTop + box.clientHeight) box.scrollTop = top - box.clientHeight / 3;
    });
  });
</script>

{#snippet section(id: string)}
  {@const status = stateOf(id)}
  <li class:passed={route.indexOf(id) < currentIndex}>
    <button
      class="dot {status}"
      class:viewing={id === viewing}
      class:skipped={app.isSkipped(id)}
      aria-label={(app.concept(id)?.title ?? id) + ', ' + t(labels[status])}
      title={app.concept(id)?.title ?? id}
      onclick={() => app.view(id)}
    ></button>
  </li>
{/snippet}

{#if variant === 'track'}
  <div class="mini track" bind:this={box}>
    {#each chapters as chapter, index (chapter.id)}
      {@const total = chapter.concept_ids.length}
      {@const here = chapter.concept_ids.indexOf(app.currentId ?? '')}
      {@const seen = viewing ? chapter.concept_ids.indexOf(viewing) : -1}
      <button
        class="segment"
        class:unbuilt={!total}
        class:here={chapter.id === currentChapter}
        style:flex-grow={Math.max(total, 1)}
        aria-label={(chapter.id ? name(chapter, index) + ', ' : '') + progress(chapter)}
        title={(chapter.id ? name(chapter, index) + ' · ' : '') + progress(chapter)}
        onclick={() => chapter.id && app.viewChapter(chapter.id)}
      >
        {#if total}<span class="fill" style:height="{(studiedIn(chapter.concept_ids) / total) * 100}%"></span>{/if}
        {#if here >= 0}<span class="marker" style:top="{((here + 0.5) / total) * 100}%"></span>{/if}
        {#if seen >= 0}<span class="marker seen" style:top="{((seen + 0.5) / total) * 100}%"></span>{/if}
      </button>
    {/each}
  </div>
{:else}
  <ol class="mini stepper" bind:this={box}>
    {#each chapters as chapter, index (chapter.id)}
      {@const total = chapter.concept_ids.length}
      {@const done = studiedIn(chapter.concept_ids)}
      <li class="chapter" class:open={chapter.id === openChapter}>
        {#if chapters.length > 1}
          <button
            class="ring"
            class:here={chapter.id === currentChapter}
            class:unbuilt={!total}
            class:done={total > 0 && done === total}
            style:--progress="{total ? (done / total) * 360 : 0}deg"
            aria-label={name(chapter, index) + ', ' + progress(chapter)}
            title={name(chapter, index) + ' · ' + progress(chapter)}
            onclick={() => app.viewChapter(chapter.id)}
          ><span aria-hidden="true">{index + 1}</span></button>
        {/if}
        {#if chapter.id === openChapter && total}
          {@const shown = windowed(chapter.concept_ids)}
          <ol class="sections">
            {#if shown.before}<li class="more" aria-hidden="true">+{shown.before}</li>{/if}
            {#each shown.ids as id (id)}
              {@render section(id)}
            {/each}
            {#if shown.after}<li class="more" aria-hidden="true">+{shown.after}</li>{/if}
          </ol>
        {/if}
      </li>
    {/each}
  </ol>
{/if}

<style>
  .mini {
    display: none;
  }

  @media (min-width: 56.01rem) {
    @container stage (max-width: 66rem) {
      /* The capsule: centred in the column by auto margins while it fits, scrolling inside itself when it does not. */
      .mini {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: var(--capsule);
        max-height: calc(100% - 2rem);
        margin: auto;
        padding: 0.7rem 0;
        overflow-y: auto;
        scrollbar-width: none;
        list-style: none;
        border: 1px solid var(--rule);
        border-radius: 999px;
        background: var(--sheet);
        box-shadow: 0 1px 3px var(--shadow-near);
        pointer-events: auto;
        transition: border-color var(--quick) ease;
      }

      .mini:hover {
        border-color: var(--rule-strong);
      }

      button {
        position: relative;
        display: block;
        padding: 0;
        border: 0;
        background: none;
        cursor: pointer;
      }

      /* Track: a chapter is a segment as long as its share of the sections, filled by the share studied. */
      .track {
        gap: 4px;
        height: min(24rem, calc(100% - 4rem));
        overflow: visible;
      }

      .segment {
        flex-basis: 0;
        flex-shrink: 1;
        width: 0.4rem;
        min-height: 0.45rem;
        border-radius: 999px;
        background: var(--rule-strong);
        overflow: visible;
        transition: width var(--quick) var(--ease-out);
      }

      .segment:hover {
        width: 0.6rem;
      }

      .segment.unbuilt {
        flex-grow: 1;
        max-height: 1rem;
        background: repeating-linear-gradient(var(--rule-strong) 0 3px, transparent 3px 6px);
      }

      .fill {
        position: absolute;
        inset: 0 0 auto;
        border-radius: 999px;
        background: var(--accent);
      }

      .marker {
        position: absolute;
        left: 50%;
        width: 0.8rem;
        height: 0.8rem;
        border: 2px solid var(--accent);
        border-radius: 50%;
        background: var(--marker);
        box-shadow: 0 0 0 3px var(--marker-wash);
        transform: translate(-50%, -50%);
      }

      .marker.seen {
        width: 0.65rem;
        height: 0.65rem;
        background: var(--sheet);
        box-shadow: 0 0 0 3px var(--accent-wash);
      }

      /* Stepper: a ring per chapter, filled by the share studied; the chapter in view lists its sections. */
      .stepper {
        gap: 0;
      }

      /* A chapter is a numbered badge on the spine, so it never reads as a section; the chapter in view hangs its
         sections below it in a tray of their own. */
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

      /* The badge's rim fills with the share of the chapter studied. */
      .ring {
        display: grid;
        place-items: center;
        width: 1.4rem;
        height: 1.4rem;
        border-radius: 50%;
        background: conic-gradient(var(--accent) var(--progress), var(--rule-strong) 0);
        font: 600 0.66rem/1 var(--sans);
        font-variant-numeric: tabular-nums;
        color: var(--pencil);
        transition: transform var(--quick) var(--ease-out);
      }

      .ring::after {
        content: '';
        position: absolute;
        inset: 2.5px;
        border-radius: 50%;
        background: var(--sheet);
      }

      .ring span {
        position: relative;
        z-index: 1;
      }

      .ring.here {
        color: var(--ink);
      }

      .ring.here::after {
        background: var(--marker);
      }

      /* A finished chapter is solid. */
      .ring.done {
        color: var(--on-accent);
      }

      .ring.done::after {
        content: none;
      }

      .ring.unbuilt {
        background: none;
        border: 1.5px dashed var(--rule-strong);
      }

      .ring.unbuilt::after {
        content: none;
      }

      .ring:hover {
        transform: scale(1.12);
      }

      .open > .ring {
        box-shadow: 0 0 0 3px var(--accent-wash);
      }

      .sections {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 1.75rem;
        margin: 0.3rem 0 0.1rem;
        padding: 0.3rem 0;
        list-style: none;
        border-radius: 999px;
        background: var(--accent-wash);
      }

      .sections li {
        position: relative;
      }

      /* Within the open chapter the dots sit on a track filled up to where the learner is. */
      .sections li:not(:last-child)::after {
        content: '';
        position: absolute;
        top: 50%;
        left: calc(50% - 1px);
        width: 2px;
        height: 100%;
        background: var(--rule);
      }

      .sections li.passed:not(:last-child)::after {
        background: var(--accent);
      }

      .more {
        font-size: 0.65rem;
        line-height: 1.2rem;
        color: var(--pencil);
        font-variant-numeric: tabular-nums;
      }

      .dot {
        z-index: 1;
        width: 1.75rem;
        height: 1.35rem;
      }

      .dot::after {
        content: '';
        position: absolute;
        inset: 50% auto auto 50%;
        width: 0.6rem;
        height: 0.6rem;
        border: 2px solid var(--rule-strong);
        border-radius: 50%;
        background: var(--sheet);
        transform: translate(-50%, -50%);
        transition: transform var(--quick) var(--ease-out);
      }

      .dot:hover::after {
        transform: translate(-50%, -50%) scale(1.25);
      }

      .dot.visited::after {
        border-color: var(--accent);
        background: var(--accent);
      }

      .dot.skipped::after {
        border-color: var(--caution);
        background: var(--sheet);
      }

      .dot.current::after {
        width: 0.75rem;
        height: 0.75rem;
        border-color: var(--accent);
        background: var(--marker);
        box-shadow: 0 0 0 3px var(--marker-wash);
      }

      .dot.viewing:not(.current)::after {
        box-shadow: 0 0 0 3px var(--accent-wash);
      }
    }
  }
</style>
