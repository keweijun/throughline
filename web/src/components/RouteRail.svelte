<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import CodexLink from './CodexLink.svelte';

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

  // The chapter being studied stays open; the learner can open or close any other.
  let toggled = $state<Record<string, boolean>>({});
  const expanded = (id: string) => toggled[id] ?? (id === currentChapter || id === app.chapterOf(app.viewingId)?.id || id === app.viewingChapter);
  const studied = (ids: string[]) => ids.filter((id) => app.hasLesson(id)).length;
</script>

{#snippet section(id: string)}
  {@const index = route.indexOf(id)}
  {@const concept = app.concept(id)}
  {@const status = stateOf(id, index)}
  {@const count = exercises.get(id)}
  {@const waiting = saved.get(id)}
  {@const skipped = app.isSkipped(id)}
  <li class={status} class:passed={index < currentIndex} class:arriving={id === arriving}>
    <span class="node" aria-hidden="true"></span>
    <button
      class:viewing={id === app.viewingId && !app.viewingChapter && !app.reviewOpen}
      aria-current={id === app.viewingId && !app.viewingChapter && !app.reviewOpen ? 'page' : undefined}
      onclick={() => app.view(id)}
    >
      <span class="name">{concept?.title ?? id}{#if app.bookmark(id)}<span class="star" aria-hidden="true" title={t("Bookmarked")}> ★</span><span class="visually-hidden">, {t("Bookmarked")}</span>{/if}</span>
      {#if status === 'current' || count || waiting || skipped || prepared.has(id)}
        <span class="meta">
          {#if status === 'current'}<span>{t("You are here")}</span>{/if}
          {#if skipped && status !== 'current'}<span class="skipped">{t("Skipped")}</span>{/if}
          {#if count}<span>{t("{solved}/{total} exercises solved", { solved: count.solved, total: count.total })}</span>{/if}
          {#if waiting}<span class="saved">{waiting === 1 ? t("1 saved question") : t("{count} saved questions", { count: waiting })}</span>{/if}
          {#if prepared.has(id) && status !== 'current'}<span>{t("Prepared")}</span>{/if}
        </span>
      {/if}
      <span class="visually-hidden">{diagnostic(label[status])}</span>
    </button>
  </li>
{/snippet}

<nav id="route" class="rail" class:open={app.routeOpen} aria-label={t("Course route")}>
  <h2>{t("Route")}</h2>
  {#if chapters.length}
    <ol class="chapters">
      {#each chapters as chapter, number (chapter.id)}
        {@const open = expanded(chapter.id)}
        <li class="chapter" class:here={chapter.id === currentChapter}>
          <div class="chapter-head">
            <button
              class="toggle"
              aria-expanded={open}
              aria-controls="chapter-{chapter.id}"
              aria-label={open ? t("Collapse chapter") : t("Expand chapter")}
              disabled={!chapter.concept_ids.length}
              onclick={() => (toggled[chapter.id] = !open)}
            ><span aria-hidden="true">{open ? '▾' : '▸'}</span></button>
            <button
              class="chapter-name"
              class:viewing={app.viewingChapter === chapter.id && !app.reviewOpen}
              aria-current={app.viewingChapter === chapter.id && !app.reviewOpen ? 'page' : undefined}
              onclick={() => app.viewChapter(chapter.id)}
            >
              <span class="name">{t("Chapter {number}", { number: number + 1 })} · {chapter.title}</span>
              <span class="meta">
                {#if chapter.concept_ids.length}
                  <span>{t("{studied}/{total} sections studied", { studied: studied(chapter.concept_ids), total: chapter.concept_ids.length })}</span>
                {:else if ['queued', 'building'].includes(app.buildOf(chapter.id)?.status ?? '')}
                  <span class="building"><span class="live-dot" aria-hidden="true"></span>{t("Building…")}</span>
                {:else}
                  <span>{t("Not built yet")}</span>
                {/if}
              </span>
            </button>
          </div>
          {#if open && chapter.concept_ids.length}
            <ol id="chapter-{chapter.id}">
              {#each chapter.concept_ids as id (id)}
                {@render section(id)}
              {/each}
            </ol>
          {/if}
        </li>
      {/each}
    </ol>
  {:else}
    <ol>
      {#each route as id (id)}
        {@render section(id)}
      {/each}
    </ol>
  {/if}
  {#if course}
    <section class="codex" aria-labelledby="codex-title">
      <h3 id="codex-title">{t('Change this course in Codex')}</h3>
      <CodexLink prompt={t('$throughline add these files to the course {course}: ', { course: course.name })}>{t('Add files in Codex')}</CodexLink>
      {#if course.needs_review}
        <CodexLink prompt={t('$throughline review the pages that still need review in the course {course}', { course: course.name })}>
          {t('Review {count} locations in Codex', { count: course.needs_review })}
        </CodexLink>
      {/if}
    </section>
  {/if}
</nav>

<style>
  .rail {
    --node: 0.8rem;
    --gutter: 1.75rem;
    position: sticky;
    top: 0;
    max-height: calc(100dvh - var(--topbar));
    overflow-y: auto;
    padding: 2.5rem 0.75rem 2rem clamp(0.75rem, 2vw, 1.5rem);
  }

  h2 {
    margin: 0 0 0.75rem var(--gutter);
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  ol {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    position: relative;
    display: grid;
    grid-template-columns: var(--gutter) minmax(0, 1fr);
    align-items: start;
    padding-bottom: 0.25rem;
  }

  /* Connector from this node to the next; both share the gutter centre, so they always line up. */
  li:not(:last-child)::before {
    content: '';
    position: absolute;
    left: calc(var(--gutter) / 2 - 1px);
    top: calc(0.62rem + var(--node) / 2);
    bottom: calc(-0.62rem - var(--node) / 2);
    width: 2px;
    background: linear-gradient(var(--accent), var(--accent)) top / 100% var(--fill, 0%) no-repeat, var(--rule);
    transition: background-size 0.7s cubic-bezier(0.3, 0, 0.2, 1);
  }

  li.passed::before {
    --fill: 100%;
  }

  .node {
    transition:
      background-color var(--settle) ease,
      border-color var(--settle) ease,
      box-shadow var(--settle) ease;
    position: relative;
    z-index: 1;
    justify-self: center;
    width: var(--node);
    height: var(--node);
    margin-top: 0.62rem;
    border: 2px solid var(--rule-strong);
    border-radius: 50%;
    background: var(--ground);
    transition: background-color 0.3s, border-color 0.3s;
  }

  .visited .node {
    border-color: var(--accent);
    background: var(--accent);
  }

  .current .node {
    border-color: var(--accent);
    background: var(--marker);
    box-shadow: 0 0 0 4px var(--marker-wash);
  }

  .arriving .node {
    animation: arrive 0.5s 0.55s cubic-bezier(0.3, 1.6, 0.5, 1) backwards;
  }

  @keyframes arrive {
    from {
      transform: scale(0.4);
      box-shadow: 0 0 0 0 var(--marker-wash);
    }
  }

  button {
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
  }

  button:hover {
    background: color-mix(in srgb, var(--accent-wash) 60%, transparent);
  }

  button.viewing {
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

  .chapters > li {
    display: block;
    padding-bottom: 0;
  }

  .chapters > li::before {
    content: none;
  }

  .chapters > li + li {
    margin-top: 0.6rem;
  }

  .chapter-head {
    display: grid;
    grid-template-columns: var(--gutter) minmax(0, 1fr);
    align-items: start;
  }

  .toggle {
    justify-self: center;
    padding: 0.4rem 0;
    color: var(--pencil);
  }

  .toggle:disabled {
    visibility: hidden;
  }

  .toggle:hover {
    background: transparent;
    color: var(--ink);
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

  .chapter ol {
    margin-top: 0.15rem;
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

  @media (max-width: 56rem) {
    .rail {
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
