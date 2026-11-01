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

  function jump(part: CoursePart) {
    document.getElementById(`course-${part}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

    <nav class="parts" aria-label={t('On this page')}>
      {#each parts as part (part.id)}
        <button class="btn btn-quiet btn-small" onclick={() => jump(part.id)}>{part.label()}</button>
      {/each}
      <button class="btn btn-small back" onclick={() => (app.courseOpen = false)}>{t('Back to reading')}</button>
    </nav>
  </header>

  <!-- Studio is course-level (ADR 0017): the first part of the page. Where Codex cannot run it, the hand-offs open a
       Codex chat instead (ADR 0016). -->
  <section class="part" id="course-studio" aria-label={t('Change this course')}>
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
      <!-- Studio scrolls inside its own frame, so its writing box stays in view and the parts below stay reachable. -->
      <div class="studio-frame">
        <Studio active={app.courseOpen} />
      </div>
    {/if}
  </section>

  <section class="part" id="course-memory" aria-label={t('Course memory')}>
    <Memory />
  </section>

  <section class="part" id="course-sources" aria-labelledby="course-sources-title">
    <h2 id="course-sources-title">{t('Sources')}</h2>
    <p class="lead">{t('Every document in the course; choose one to open it in the reader.')}</p>
    <SourceList page />
  </section>

  <section class="part" id="course-notes" aria-labelledby="course-notes-title">
    <h2 id="course-notes-title">{t('Your notes')}</h2>
    <p class="lead">
      {notes === 1 ? t('1 highlight, note or bookmark') : t('{count} highlights, notes and bookmarks', { count: notes })}.
      {t('Export them as one Markdown file, by chapter and section; notes with images come as a ZIP with an images folder.')}
    </p>
    <div class="actions">
      <button class="btn btn-small" onclick={() => app.openPanel('notes')}>{t('Open notes')}</button>
      <button class="btn btn-small" disabled={!notes || exporting} onclick={exportAll}>{exporting ? t('Exporting…') : t('Export notes')}</button>
    </div>
  </section>
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

  .parts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
  }

  .back {
    margin-left: auto;
  }

  .part {
    display: grid;
    gap: 0.75rem;
    scroll-margin-top: 1.5rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  /* Memory brings its own heading from the side panel; on the page it reads like the other parts' headings. */
  #course-memory :global(#memory-title) {
    font-family: var(--serif);
    font-size: var(--step-1);
  }

  /* The same quiet intro the memory view brings with it, so the parts read alike. */
  .lead {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  /* A fixed height, which Studio fills with its box at the bottom: content loading inside never shifts the box. */
  .studio-frame {
    display: flex;
    flex-direction: column;
    height: min(72vh, 46rem);
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
