<script lang="ts">
  import { slide } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import CodexLink from './CodexLink.svelte';
  import FoldedRoute from './FoldedRoute.svelte';

  const route = $derived(app.state?.curriculum.route ?? []);
  const currentIndex = $derived(app.routeIndex(app.currentId));
  const saved = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const item of app.state?.deferred_explanations ?? []) {
      if (item.status === 'pending') counts.set(item.target_concept_id, (counts.get(item.target_concept_id) ?? 0) + 1);
    }
    return counts;
  });
  const prepared = $derived(
    new Set((app.state?.preparation.jobs ?? []).filter((j) => j.status === 'ready').map((j) => j.concept_id)),
  );
  const exercises = $derived.by(() => {
    const counts = new Map<string, { solved: number; total: number }>();
    for (const task of app.state?.practice.tasks ?? []) {
      if (task.chapter_id || task.status === 'skipped') continue; // a chapter quiz question counts on the chapter page, not in its anchor section; a skipped exercise not at all
      const entry = counts.get(task.concept_id) ?? { solved: 0, total: 0 };
      entry.total += 1;
      if (solved(task)) entry.solved += 1;
      counts.set(task.concept_id, entry);
    }
    return counts;
  });

  // The arrival animation plays only when the learner moves on, not on every page load.
  let previous: string | null = null;
  let arriving = $state<string | null>(null);
  $effect(() => {
    const id = app.currentId;
    if (previous && id && id !== previous) {
      arriving = id;
      setTimeout(() => arriving === id && (arriving = null), 1400);
    }
    previous = id;
  });

  function stateOf(id: string, index: number) {
    if (id === app.currentId) return 'current';
    if (index < currentIndex || app.hasLesson(id)) return 'visited';
    return 'upcoming';
  }

  const label = { current: 'Current section', visited: 'Visited', upcoming: 'Not started' };

  const course = $derived(app.libraryCourse);
  const chapters = $derived(app.chapters);
  const currentChapter = $derived(app.chapterOf(app.currentId)?.id);

  const studied = (ids: string[]) => ids.filter((id) => app.studied(id)).length;
  // Folding needs room to unfold into; without it the route stays folded and opens on hover.
  const foldable = $derived(!app.stageNarrow && !app.phone);

  // Folding leaves the pointer where the full route was; the drawer stays shut until the pointer has left the rail,
  // so folding does not look like it reopened at once.
  let nav = $state<HTMLElement>();
  let resting = $state(false);
  let wasFolded = app.folded;
  $effect(() => {
    if (app.folded && !wasFolded && nav?.matches(':hover')) resting = true;
    wasFolded = app.folded;
  });
  $effect(() => {
    if (!resting) return;
    const away = (event: PointerEvent) => {
      if (!nav?.contains(event.target as Node)) resting = false;
    };
    window.addEventListener('pointermove', away);
    return () => window.removeEventListener('pointermove', away);
  });

  // The full route turns into the hidden drawer the moment the route folds, without the delayed fade that keeps the
  // drawer from flickering on hover; that fade would show it for a moment. Set before the update, so both apply at once.
  let entering = $state(false);
  let foldedBefore = app.folded;
  $effect.pre(() => {
    const folded = app.folded;
    if (folded && !foldedBefore) {
      entering = true;
      requestAnimationFrame(() => requestAnimationFrame(() => (entering = false)));
    }
    foldedBefore = folded;
  });

  // The route keeps what the learner is looking at in view: when it opens, folds or unfolds, and whenever they move
  // or look elsewhere. Folded, the drawer scrolls instead of the rail, and is checked again each time it opens, since
  // the learner may have scrolled it away. Opening and closing chapters slides the trays, so look again once they settle.
  let full = $state<HTMLElement>();
  function reveal() {
    requestAnimationFrame(() => {
      const box = app.folded ? full : nav;
      if (!box) return;
      // What is open on the page, else the current section, else the chapter being studied. Positions come from the
      // screen, since each row is positioned and offsetTop would count from the row instead of the scrolling box.
      const item =
        box.querySelector<HTMLElement>('[aria-current="page"]') ??
        box.querySelector<HTMLElement>('.current .entry') ??
        box.querySelector<HTMLElement>('.chapter.here .chapter-name');
      if (!item) return;
      const top = item.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
      if (top < box.scrollTop || top + item.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = top - box.clientHeight / 3;
    });
  }
  $effect(() => {
    void [app.viewingId, app.viewingChapter, app.reviewOpen, app.currentId, app.folded, app.routeOpen, nav, full];
    reveal();
    const settled = setTimeout(reveal, 260);
    return () => clearTimeout(settled);
  });
</script>

{#snippet section(id: string)}
  {@const index = route.indexOf(id)}
  {@const concept = app.concept(id)}
  {@const status = stateOf(id, index)}
  {@const count = exercises.get(id)}
  {@const waiting = saved.get(id)}
  {@const skipped = app.isSkipped(id)}
  {@const step = status === 'current' ? app.stepProgress(id) : null}
  {@const viewing = id === app.viewingId && !app.viewingChapter && !app.reviewOpen}
  <li class={status} class:passed={index < currentIndex} class:arriving={id === arriving}>
    <span class="node" aria-hidden="true"><span class="route-dot {status}" class:viewing class:skipped></span></span>
    <button class="entry" class:viewing aria-current={viewing ? 'page' : undefined} onclick={() => app.view(id)}>
      <span class="name">{concept?.title ?? id}{#if app.bookmark(id)}<span class="star" aria-hidden="true" title={t("Bookmarked")}> ★</span><span class="visually-hidden">, {t("Bookmarked")}</span>{/if}</span>
      {#if status === 'current' || count || waiting || skipped || prepared.has(id)}
        <span class="meta">
          {#if status === 'current'}<span>{t("You are here")}</span>{/if}
          {#if step}<span>{t("Step {number} of {total}", step)}</span>{/if}
          {#if skipped && status !== 'current'}<span class="skipped">{t("Skipped")}</span>{/if}
          {#if count}<span>{t("{solved}/{total} exercises solved", { solved: count.solved, total: count.total })}</span>{/if}
          {#if waiting}<span class="saved">{waiting === 1 ? t("1 saved question") : t("{count} saved questions", { count: waiting })}</span>{/if}
          {#if prepared.has(id) && status !== 'current'}<span>{t("Lesson ready")}</span>{/if}
        </span>
      {/if}
      <span class="visually-hidden">{diagnostic(label[status])}</span>
    </button>
  </li>
{/snippet}

<nav id="route" class="rail" class:open={app.routeOpen} class:folded={app.folded} class:resting class:entering aria-label={t("Course route")} onpointerenter={() => app.folded && reveal()} bind:this={nav}>
  {#if app.folded}<FoldedRoute />{/if}
  <div class="full" bind:this={full}>
    <div class="head">
      <h2>{t("Route")}</h2>
      {#if foldable}
        <button
          class="fold"
          aria-label={app.folded ? t('Unfold the route') : t('Fold the route')}
          title={app.folded ? t('Unfold the route (r)') : t('Fold the route (r)')}
          onclick={() => app.toggleRoute()}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d={app.folded ? 'M6 4l4 4-4 4' : 'M10 4L6 8l4 4'} fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
      {/if}
    </div>
    {#if chapters.length}
      <ol class="chapters">
        {#each chapters as chapter, number (chapter.id)}
          {@const open = app.chapterOpen(chapter.id)}
          {@const total = chapter.concept_ids.length}
          {@const done = studied(chapter.concept_ids)}
          <li class="chapter" class:here={chapter.id === currentChapter}>
            <div class="chapter-head">
              <!-- The chapter's badge is the folded route's badge; here it also opens and closes the chapter. -->
              <button
                class="route-badge"
                class:open={open && total > 0}
                class:here={chapter.id === currentChapter}
                class:unbuilt={!total}
                class:done={total > 0 && done === total}
                style:--progress="{total ? (done / total) * 360 : 0}deg"
                aria-expanded={total ? open : undefined}
                aria-controls={total ? `chapter-${chapter.id}` : undefined}
                aria-label={open ? t("Collapse chapter") : t("Expand chapter")}
                title={t("Chapter {number}", { number: number + 1 }) + ' · ' + chapter.title}
                disabled={!total}
                onclick={() => app.toggleChapter(chapter.id)}
              ><span aria-hidden="true">{number + 1}</span></button>
              <button
                class="entry chapter-name"
                class:viewing={app.viewingChapter === chapter.id && !app.reviewOpen}
                aria-current={app.viewingChapter === chapter.id && !app.reviewOpen ? 'page' : undefined}
                onclick={() => app.viewChapter(chapter.id)}
              >
                <span class="name">{t("Chapter {number}", { number: number + 1 })} · {chapter.title}</span>
                <span class="meta">
                  {#if total}
                    <span>{t("{studied}/{total} sections studied", { studied: done, total })}</span>
                  {:else if ['queued', 'building'].includes(app.buildOf(chapter.id)?.status ?? '')}
                    <span class="building"><span class="live-dot" aria-hidden="true"></span>{t("Building…")}</span>
                  {:else}
                    <span>{t("Not built yet")}</span>
                  {/if}
                </span>
              </button>
            </div>
            {#if open && total}
              <ol class="tray" id="chapter-{chapter.id}" transition:slide={{ duration: prefersReducedMotion.current ? 0 : 220 }}>
                {#each chapter.concept_ids as id (id)}
                  {@render section(id)}
                {/each}
              </ol>
            {/if}
          </li>
        {/each}
      </ol>
    {:else}
      <ol class="tray">
        {#each route as id (id)}
          {@render section(id)}
        {/each}
      </ol>
    {/if}
    {#if course}
      <section class="codex" aria-labelledby="codex-title">
        <h3 id="codex-title">{t('Change this course in Studio')}</h3>
        <CodexLink prompt={t('$throughline add these files to the course {course}: ', { course: course.name })}>{t('Add files in Studio')}</CodexLink>
        {#if course.needs_review}
          <CodexLink prompt={t('$throughline review the pages that still need review in the course {course}', { course: course.name })}>
            {t('Check {count} source locations in Studio', { count: course.needs_review })}
          </CodexLink>
        {/if}
      </section>
    {/if}
  </div>
</nav>

<style>
  .rail {
    --gutter: 1.75rem;
    --capsule: 2.25rem;
    --marker-ground: var(--ground);
    position: sticky;
    top: 0;
    max-height: calc(100dvh - var(--topbar));
    overflow-y: auto;
    padding: 2.5rem 0.75rem 2rem clamp(0.75rem, 2vw, 1.5rem);
  }

  /* Unfolding brings the labels back in rather than snapping them. */
  .rail:not(.folded) .full {
    animation: enter-fade var(--settle) ease;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin: 0 0 0.75rem var(--gutter);
  }

  h2 {
    margin: 0;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .fold {
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: none;
    color: var(--pencil);
    cursor: pointer;
    transition:
      color var(--quick) ease,
      background-color var(--quick) ease;
  }

  .fold:hover {
    background: var(--accent-wash);
    color: var(--accent);
  }

  ol {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .tray > li {
    position: relative;
    display: grid;
    grid-template-columns: var(--gutter) minmax(0, 1fr);
    align-items: start;
    padding-bottom: 0.25rem;
  }

  /* An open chapter's sections sit in a tray along the spine, as in the folded route. */
  .tray {
    position: relative;
    isolation: isolate;
    margin-top: 0.3rem;
  }

  .tray::before {
    content: '';
    position: absolute;
    z-index: -1;
    top: 0.1rem;
    bottom: 0.1rem;
    left: 0.15rem;
    width: calc(var(--gutter) - 0.3rem);
    border-radius: 999px;
    background: var(--accent-wash);
    animation: tray-in var(--settle) var(--ease-out);
  }

  @keyframes tray-in {
    from {
      opacity: 0;
    }
  }

  /* Connector from this dot to the next; both share the gutter centre, so they always line up. */
  .tray > li:not(:last-child)::before {
    content: '';
    position: absolute;
    left: calc(var(--gutter) / 2 - 1px);
    top: 1rem;
    bottom: -1rem;
    width: 2px;
    background: linear-gradient(var(--accent), var(--accent)) top / 100% var(--fill, 0%) no-repeat, var(--rule-strong);
    transition: background-size 0.7s cubic-bezier(0.3, 0, 0.2, 1);
  }

  .tray > li.passed::before {
    --fill: 100%;
  }

  .node {
    position: relative;
    z-index: 1;
    display: grid;
    place-items: center;
    height: 2rem;
  }

  .tray > li:hover .route-dot {
    transform: scale(1.25);
  }

  .arriving .route-dot {
    animation: arrive 0.5s 0.55s cubic-bezier(0.3, 1.6, 0.5, 1) backwards;
  }

  @keyframes arrive {
    from {
      transform: scale(0.4);
      box-shadow: 0 0 0 0 var(--marker-wash);
    }
  }

  .entry {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
    padding: 0.4rem 0.55rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    text-align: left;
    cursor: pointer;
    color: var(--ink-soft);
    transition:
      background-color var(--quick) ease,
      color var(--quick) ease;
  }

  .entry:hover {
    background: color-mix(in srgb, var(--accent-wash) 60%, transparent);
    color: var(--ink);
  }

  .entry.viewing {
    background: var(--accent-wash);
    color: var(--ink);
  }

  .name {
    font-size: var(--step-0);
    line-height: 1.35;
  }

  .current .name {
    font-weight: 600;
    color: var(--ink);
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .meta .saved {
    color: var(--accent);
  }

  .meta .skipped {
    color: var(--caution);
  }

  .meta .building {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--accent);
  }

  .chapter + .chapter {
    margin-top: 0.6rem;
  }

  .chapter-head {
    display: grid;
    grid-template-columns: var(--gutter) minmax(0, 1fr);
    align-items: start;
  }

  .chapter-head .route-badge {
    justify-self: center;
    margin-top: 0.4rem;
  }

  .chapter-name .name {
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--ink-soft);
  }

  .chapter.here .chapter-name .name {
    color: var(--ink);
  }

  .codex {
    display: grid;
    justify-items: start;
    gap: 0.3rem;
    margin: 1.75rem 0 0 var(--gutter);
    font-size: var(--step--1);
  }

  .codex h3 {
    font-family: var(--sans);
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .star {
    color: var(--mine);
  }

  /* Folded, the route is FoldedRoute's capsule centred in the column. Pointing at the capsule opens the full route as a
     drawer beside it, which slides in, and waits a moment before closing so brushing past its edge does not flicker. */
  .rail.folded {
    z-index: 20;
    display: flex;
    width: var(--rail-folded);
    height: calc(100dvh - var(--topbar));
    max-height: none;
    overflow: visible;
    padding: 0;
    pointer-events: none;
  }

  .rail.folded .full {
    --marker-ground: var(--sheet);
    position: absolute;
    top: 0;
    bottom: 0;
    left: calc(50% + var(--capsule) / 2 - 1px);
    width: var(--rail);
    overflow-y: auto;
    padding: 2.5rem 0.75rem 2rem;
    background: var(--sheet);
    border-right: 1px solid var(--rule);
    box-shadow: var(--shadow);
    opacity: 0;
    visibility: hidden;
    transform: translateX(-0.6rem);
    transition:
      opacity var(--quick) ease 0.12s,
      transform var(--quick) ease 0.12s,
      visibility 0s linear calc(var(--quick) + 0.12s);
  }

  .rail.folded.entering .full {
    transition: none;
  }

  .rail.folded:not(.resting):has(:global(.mini:hover), .full:hover) .full {
    opacity: 1;
    visibility: visible;
    transform: none;
    pointer-events: auto;
    transition:
      opacity var(--quick) ease,
      transform var(--settle) var(--ease-out),
      visibility 0s;
  }

  @media (prefers-reduced-motion: reduce) {
    .rail .full,
    .rail.folded .full,
    .tray::before,
    .arriving .route-dot {
      animation: none;
      transition: none;
    }
  }

  @media (max-width: 56rem) {
    .rail {
      --marker-ground: var(--sheet);
      position: fixed;
      top: var(--topbar);
      bottom: 0;
      left: 0;
      z-index: 35;
      width: min(20rem, 86vw);
      max-height: none;
      padding-top: 1.5rem;
      background: var(--sheet);
      border-right: 1px solid var(--rule);
      box-shadow: var(--shadow);
      transform: translateX(-102%);
      transition: transform 0.2s ease;
      visibility: hidden;
    }

    .rail.open {
      transform: none;
      visibility: visible;
    }
  }
</style>
