<script lang="ts">
  import { tick } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app, type CoursePart } from '../lib/store.svelte';
  import { exportNotes } from '../lib/notes';
  import CodexLink from './CodexLink.svelte';
  import TeachingPreferences from './TeachingPreferences.svelte';
  import SourceList from './SourceList.svelte';
  import Studio from './Studio.svelte';
  import { studio } from '../lib/studio.svelte';

  // The course as a whole (ADR 0017): changing it, what the teacher remembers, its sources and the learner's notes.
  // Everything here is about the course rather than the section being read, which keeps it out of the side panel.
  const course = $derived(app.libraryCourse);
  const route = $derived(app.state?.curriculum.route ?? []);
  const sources = $derived(app.state?.sources.length ?? 0);
  const notes = $derived(app.state?.annotations.length ?? 0);
  const suggested = $derived((app.state?.memory ?? []).some((e) => e.status === 'suggested'));
  const current = $derived(app.chapterOf(app.currentId));
  const currentNumber = $derived(app.chapters.findIndex((c) => c.id === current?.id) + 1);
  const currentDone = $derived(current ? current.concept_ids.filter((id) => app.studied(id)).length : 0);

  // One segment per chapter, as wide as its sections, filled as they are studied. A course without chapters is one.
  const strip = $derived(
    (app.chapters.length ? app.chapters : [{ id: '', title: app.state?.course.title ?? '', concept_ids: route }]).map((chapter, i) => {
      const done = chapter.concept_ids.filter((id) => app.studied(id)).length;
      return { id: chapter.id, number: i + 1, title: chapter.title, total: chapter.concept_ids.length, done };
    }),
  );

  const parts: { id: CoursePart; label: () => string }[] = [
    { id: 'studio', label: () => (studio.available === false ? t('Change this course') : t('Studio')) },
    { id: 'sources', label: () => t('Sources') },
    { id: 'notes', label: () => t('Your notes') },
  ];

  let exporting = $state(false);
  async function exportAll() {
    exporting = true;
    await exportNotes();
    exporting = false;
  }

  // Once the learner writes to Studio, the course's header steps aside: the page scrolls it away under the pinned tabs
  // and Studio's frame grows upward by as much, so its box stays exactly where it was. Leaving the tab gives it back.
  let grown = $state<number | null>(null);
  // A page shorter than the window cannot scroll that far by itself; this much room under the frame lets it.
  let room = $state(0);
  let barHeight = $state(0);
  let frame = $state<HTMLElement>();

  async function startWork() {
    const stage = document.getElementById('stage');
    if (grown !== null || !stage || !frame) return;
    const gap = parseFloat(getComputedStyle(frame.closest('.page')!).rowGap) || 0;
    const by = Math.max(0, Math.round(frame.getBoundingClientRect().top - stage.getBoundingClientRect().top - barHeight - gap));
    grown = by;
    await tick();
    const from = stage.scrollTop;
    stage.scrollBy({ top: by, behavior: 'instant' });
    const short = by - (stage.scrollTop - from);
    if (short < 1) return;
    room = short;
    await tick();
    stage.scrollBy({ top: short, behavior: 'instant' });
  }

  $effect(() => {
    if (app.courseOpen && app.coursePart === 'studio') return;
    grown = null;
    room = 0;
  });

  // A turn that starts by any other way than the box, such as a hand-off from a lesson, counts as writing too.
  $effect(() => {
    if (studio.running && app.courseOpen && app.coursePart === 'studio') void startWork();
  });

  // One tab at a time at full height, so Studio has the room and nothing scrolls inside something else that scrolls.
  function onTabKey(event: KeyboardEvent) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const at = parts.findIndex((p) => p.id === app.coursePart);
    const next = parts[(at + step + parts.length) % parts.length];
    app.coursePart = next.id;
    document.getElementById(`course-tab-${next.id}`)?.focus();
  }
</script>

<article class="page" aria-labelledby="course-title">
  <header class="head">
    <h1 id="course-title">{app.state?.course.title}</h1>
    {#if course?.goal}<p class="intro" title={course.goal}>{course.goal}</p>{/if}

    <!-- The whole route at a glance; a segment opens its chapter. -->
    <div class="glance">
      <ol class="strip" aria-label={t('Chapters')}>
        {#each strip as segment (segment.id || 'all')}
          <li style:flex-grow={Math.max(segment.total, 1)}>
            <button
              class="segment"
              class:current={current?.id === segment.id && !!segment.id}
              disabled={!segment.id}
              title={t('{title}: {studied} of {total} sections studied', { title: segment.title, studied: segment.done, total: segment.total })}
              aria-label={t('{title}: {studied} of {total} sections studied', { title: segment.title, studied: segment.done, total: segment.total })}
              onclick={() => app.viewChapter(segment.id)}
            >
              <span class="fill" style:width="{segment.total ? (segment.done / segment.total) * 100 : 0}%"></span>
            </button>
          </li>
        {/each}
      </ol>
      <!-- Overall progress is in the top bar; here, where in the route you are and how much there is. -->
      <p class="facts">
        {#if current}
          <span class="now">
            {t('{title}: {studied} of {total} sections studied', {
              title: `${t('Chapter {number}', { number: currentNumber })} · ${current.title}`,
              studied: currentDone,
              total: current.concept_ids.length,
            })}
          </span>
        {/if}
        {#if app.chapters.length}<span>{t('Chapters: {count}', { count: app.chapters.length })}</span>{/if}
        <span>{t('Sources: {count}', { count: sources })}</span>
      </p>
    </div>
  </header>

  <!-- Outside the header, so the tabs stay pinned while the header scrolls away. -->
  <div class="bar" bind:offsetHeight={barHeight}>
    <div class="tabs" role="tablist" aria-label={t('This course')} tabindex="-1" onkeydown={onTabKey}>
      {#each parts as part (part.id)}
        <button
          id="course-tab-{part.id}"
          class="tab"
          role="tab"
          aria-selected={app.coursePart === part.id}
          aria-controls="course-{part.id}"
          tabindex={app.coursePart === part.id ? 0 : -1}
          onclick={() => (app.coursePart = part.id)}
        >
          {part.label()}{#if part.id === 'studio' && suggested}<span class="dot" aria-hidden="true"></span>{/if}
        </button>
      {/each}
    </div>
  </div>

  <!-- Studio is course-level (ADR 0017): the first tab. Where Codex cannot run it, the hand-offs open a Codex chat
       instead (ADR 0016). Hidden tabs stay mounted, so each keeps its place. -->
  <div class="part" id="course-studio" role="tabpanel" aria-labelledby="course-tab-studio" hidden={app.coursePart !== 'studio'}>
    <!-- How the learner is taught stands beside Studio, where it is changed: tell Studio, and it records it here. -->
    <div class="studio-row">
    <div class="studio-main">
    {#if studio.available === false}
      <h2>{t('Change this course')}</h2>
      <p class="lead">{t('Add files, rebuild the route, check pages or change how the course is taught. Each request opens a Codex chat with it typed in; this page updates when Codex is done.')}</p>
      {#if course}
        <div class="actions">
          <CodexLink class="btn btn-small" prompt={t('$throughline add these files to the course {course}: ', { course: course.name })}>{t('Add files in Codex')}</CodexLink>
          {#if course.needs_review}
            <CodexLink class="btn btn-small" prompt={t('$throughline review the pages that still need review in the course {course}', { course: course.name })}>
              {t('Check {count} source locations in Codex', { count: course.needs_review })}
            </CodexLink>
          {/if}
          <CodexLink class="btn btn-small" chat prompt={t('$throughline in the course {course}, ', { course: course.name })}>{t('Something else in Codex')}</CodexLink>
        </div>
      {/if}
    {:else}
      <!-- Studio scrolls inside its own frame, so its writing box stays in view. -->
      <div
        class="frame studio-frame"
        data-scroller
        bind:this={frame}
        style:--grown={grown === null ? null : `${grown}px`}
        style:margin-bottom={room ? `${room}px` : null}
        onfocusin={(event) => (event.target as Element).closest('.cm-editor') && void startWork()}
      >
        <Studio active={app.courseOpen && app.coursePart === 'studio'} />
      </div>
    {/if}
    </div>
    <TeachingPreferences />
    </div>
  </div>

  <div class="part" id="course-sources" role="tabpanel" aria-labelledby="course-tab-sources" hidden={app.coursePart !== 'sources'}>
    <p class="lead">{t('Every document in the course; choose one to open it in the reader.')}</p>
    <SourceList page />
  </div>

  <div class="part" id="course-notes" role="tabpanel" aria-labelledby="course-tab-notes" hidden={app.coursePart !== 'notes'}>
    <p class="lead">
      {notes === 1 ? t('1 highlight, note or bookmark') : t('{count} highlights, notes and bookmarks', { count: notes })}.
      {t('Export them as one Markdown file, by chapter and section; notes with images come as a ZIP with an images folder.')}
    </p>
    <div class="actions">
      <button class="btn btn-small" onclick={() => app.openPanel('notes')}>{t('Open notes')}</button>
      <button class="btn btn-small" disabled={!notes || exporting} onclick={exportAll}>{exporting ? t('Exporting…') : t('Export notes')}</button>
    </div>
  </div>
</article>

<style>
  /* Fades rather than rises: `d` puts the caret in Studio's box at once, and the box never moves under the learner. */
  .page {
    animation: enter-fade var(--settle) ease;
    max-width: calc(var(--measure) + 20rem);
    margin-inline: auto;
    display: grid;
    gap: 1.5rem;
  }

  .head {
    display: grid;
    gap: 0.75rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: var(--step-3);
    font-weight: 600;
    line-height: 1.15;
  }

  /* A long goal stays two lines; the whole of it is in the tooltip. */
  .intro {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    font-family: var(--serif);
    font-size: var(--step-0);
    line-height: 1.5;
    color: var(--ink-soft);
  }

  .glance {
    display: grid;
    gap: 0.45rem;
  }

  .strip {
    display: flex;
    gap: 0.25rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .strip li {
    flex-basis: 0;
    min-width: 0.75rem;
  }

  .segment {
    position: relative;
    display: block;
    width: 100%;
    height: 0.6rem;
    padding: 0;
    overflow: hidden;
    border: 0;
    border-radius: 999px;
    background: var(--rule);
    cursor: pointer;
    transition: transform var(--quick) var(--ease-out);
  }

  .segment:disabled {
    cursor: default;
  }

  .segment:hover:not(:disabled) {
    transform: scaleY(1.5);
  }

  .segment.current {
    outline: 2px solid var(--marker);
    outline-offset: 1px;
  }

  .fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--accent);
    transition: width 0.4s var(--ease-out);
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .facts .now {
    color: var(--ink-soft);
    font-weight: 600;
  }

  /* Pinned under the top bar, so the tabs stay at hand while the header scrolls away; as close to the header as before. */
  .bar {
    position: sticky;
    top: 0;
    z-index: 3;
    display: flex;
    align-items: end;
    gap: 1rem;
    margin-top: -0.75rem;
    border-bottom: 1px solid var(--rule);
    background: var(--ground);
  }

  .tabs {
    display: flex;
    gap: 0.25rem;
  }

  .tab {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    margin-bottom: -1px;
    padding: 0.5rem 0.8rem;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: var(--ink-soft);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }

  .tab:hover {
    color: var(--ink);
  }

  .tab[aria-selected='true'] {
    border-bottom-color: var(--accent);
    color: var(--ink);
  }

  .dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    background: var(--marker);
  }

  .part {
    display: grid;
    gap: 0.75rem;
  }

  .part[hidden] {
    display: none;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  /* Studio takes the room; how the learner is taught stands beside it on a wide screen and below it otherwise. */
  .studio-row {
    display: grid;
    gap: 1.25rem;
    align-items: start;
  }

  @media (min-width: 72rem) {
    .studio-row {
      grid-template-columns: minmax(0, 1fr) 17rem;
    }
  }

  .studio-main {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
  }

  /* Studio brings its own heading; on the page its tab already names it. */
  #course-studio :global(.studio > .panel-head > .panel-bar),
  #course-studio :global(.studio > .panel-head > .panel-intro) {
    display: none;
  }

  /* The same quiet intro the memory view brings with it, so the parts read alike. */
  .lead {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  /* Studio and Memory are built for the side panel: the same surface and padding here keep their raised writing box
     and its pinned strip (.panel-foot, painted in --sheet) on one ground, aligned with what is listed above it. */
  .frame {
    display: flex;
    flex-direction: column;
    max-height: max(24rem, calc(100vh - var(--topbar) - 22rem));
    overflow-y: auto;
    padding: 1.1rem 1.1rem 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  /* Studio's frame keeps one height, which Studio fills with its box at the bottom, so content loading inside it (the
     welcome, a reopened chat) never moves the box from under the learner's pointer. */
  .studio-frame {
    height: calc(max(24rem, 100vh - var(--topbar) - 22rem) + var(--grown, 0px));
    max-height: none;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  @media (prefers-reduced-motion: reduce) {
    .segment {
      transition: none;
    }
  }

  /* A tab that comes into view fades in, as the side panel's views do. */
  .part:not([hidden]) {
    animation: enter-fade var(--quick) ease;
  }
</style>
