<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type CoursePart } from '../lib/store.svelte';
  import { exportNotes } from '../lib/notes';
  import CodexLink from './CodexLink.svelte';
  import Memory from './Memory.svelte';
  import SourceList from './SourceList.svelte';
  import Studio from './Studio.svelte';
  import { studio } from '../lib/studio.svelte';

  // The course as a whole (ADR 0017): changing it, what the teacher remembers, its sources and the learner's notes.
  // Everything here is about the course rather than the section being read, which keeps it out of the side panel.
  const course = $derived(app.libraryCourse);
  const route = $derived(app.state?.curriculum.route ?? []);
  const studied = $derived(route.filter((id) => app.studied(id)).length);
  const sources = $derived(app.state?.sources.length ?? 0);
  const notes = $derived(app.state?.annotations.length ?? 0);
  const suggested = $derived((app.state?.memory ?? []).some((e) => e.status === 'suggested'));
  const current = $derived(app.chapterOf(app.currentId));

  // One segment per chapter, as wide as its sections, filled as they are studied. A course without chapters is one.
  const strip = $derived(
    (app.chapters.length ? app.chapters : [{ id: '', title: app.state?.course.title ?? '', concept_ids: route }]).map((chapter, i) => {
      const done = chapter.concept_ids.filter((id) => app.studied(id)).length;
      return { id: chapter.id, number: i + 1, title: chapter.title, total: chapter.concept_ids.length, done };
    }),
  );

  const parts: { id: CoursePart; label: () => string }[] = [
    { id: 'studio', label: () => (studio.available === false ? t('Change this course') : t('Studio')) },
    { id: 'memory', label: () => t('Course memory') },
    { id: 'sources', label: () => t('Sources') },
    { id: 'notes', label: () => t('Your notes') },
  ];

  let exporting = $state(false);
  async function exportAll() {
    exporting = true;
    await exportNotes();
    exporting = false;
  }

  // One tab at a time at full height, so Studio and Memory, each with a writing box, never share the screen.
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
    {#if course?.goal}<p class="intro">{course.goal}</p>{/if}

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
      <p class="facts">
        <span>{t('{studied} of {total} sections studied', { studied, total: route.length })}</span>
        {#if app.chapters.length}<span>{t('Chapters: {count}', { count: app.chapters.length })}</span>{/if}
        <span>{t('Sources: {count}', { count: sources })}</span>
      </p>
    </div>

    <div class="bar">
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
            {part.label()}{#if part.id === 'memory' && suggested}<span class="dot" aria-hidden="true"></span>{/if}
          </button>
        {/each}
      </div>
      <button class="btn btn-small back" onclick={() => (app.courseOpen = false)}>{t('Back to reading')}</button>
    </div>
  </header>

  <!-- Studio is course-level (ADR 0017): the first tab. Where Codex cannot run it, the hand-offs open a Codex chat
       instead (ADR 0016). Hidden tabs stay mounted, so each keeps its place. -->
  <div class="part" id="course-studio" role="tabpanel" aria-labelledby="course-tab-studio" hidden={app.coursePart !== 'studio'}>
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
      <div class="frame">
        <Studio active={app.courseOpen} />
      </div>
    {/if}
  </div>

  <div class="part" id="course-memory" role="tabpanel" aria-labelledby="course-tab-memory" hidden={app.coursePart !== 'memory'}>
    <Memory />
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
  .page {
    max-width: var(--measure);
    margin-inline: auto;
    display: grid;
    gap: 2.5rem;
  }

  .head {
    display: grid;
    gap: 1rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: clamp(var(--step-3), 4.2vw, 2.75rem);
    font-weight: 600;
    line-height: 1.1;
  }

  .intro {
    font-family: var(--serif);
    font-size: var(--step-1);
    line-height: 1.45;
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
    transition: transform var(--quick, 120ms) ease-out;
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
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 1rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .bar {
    display: flex;
    align-items: end;
    gap: 1rem;
    border-bottom: 1px solid var(--rule);
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

  .back {
    margin: 0 0 0.4rem auto;
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

  /* Memory brings its own heading from the side panel; on the page its tab already names it. */
  #course-memory :global(.panel-bar) {
    display: none;
  }

  /* The same quiet intro the memory view brings with it, so the parts read alike. */
  .lead {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .frame {
    display: flex;
    flex-direction: column;
    max-height: max(24rem, calc(100vh - var(--topbar) - 22rem));
    overflow-y: auto;
    padding: 0 0.75rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
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
</style>
