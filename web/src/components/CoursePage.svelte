<script lang="ts">
  import { tick, untrack } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app, type CoursePart } from '../lib/store.svelte';
  import { exportNotes } from '../lib/notes';
  import CodexLink from './CodexLink.svelte';
  import TeachingPreferences from './TeachingPreferences.svelte';
  import StudioChats from './StudioChats.svelte';
  import SourceList from './SourceList.svelte';
  import SourceViewer from './SourceViewer.svelte';
  import CourseShare from './CourseShare.svelte';
  import Studio from './Studio.svelte';
  import { studio } from '../lib/studio.svelte';
  import { MediaQuery } from 'svelte/reactivity';

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
    { id: 'share', label: () => t('Share') },
  ];

  // A course started fresh from someone else's package (ADR 0020): the route was built for their goal, so the page asks
  // for the learner's own until Studio records it.
  const imported = $derived(app.state?.course.imported ?? null);
  const builtFor = $derived(app.state?.course.built_for ?? null);

  let exporting = $state(false);
  async function exportAll() {
    exporting = true;
    await exportNotes();
    exporting = false;
  }

  // Studio and an open document fill the window below the tabs, measured rather than guessed, since the header above
  // them is as tall as the course's goal and notices make it.
  // Where the tabs stand in a column beside the content; the same width as the stylesheet's.
  const wide = new MediaQuery('min-width: 70rem');

  let fill = $state(0);
  let head = $state<HTMLElement>();
  let bar = $state<HTMLElement>();
  const reading = $derived(!!app.source || app.sourceLoading);
  const filling = $derived(app.coursePart === 'studio' ? studio.available !== false : app.coursePart === 'sources' && reading);
  const shownPart = () => document.getElementById(`course-${app.coursePart}`);
  const contentTop = (node: Element, stage: HTMLElement) => node.getBoundingClientRect().top - stage.getBoundingClientRect().top + stage.scrollTop;

  function measure() {
    const stage = document.getElementById('stage');
    const part = shownPart();
    if (!stage || !part || part.hidden) return;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const bottom = parseFloat(getComputedStyle(part.closest('main')!).paddingBottom) || 0;
    fill = Math.max(24 * rem, stage.clientHeight - contentTop(part, stage) - bottom);
  }

  $effect(() => {
    const stage = document.getElementById('stage');
    if (!stage || !head) return;
    const observer = new ResizeObserver(measure);
    observer.observe(stage);
    observer.observe(head);
    return () => observer.disconnect();
  });
  $effect(() => {
    void [app.coursePart, filling];
    measure();
  });

  // Once the learner works in Studio, or opens a document, the course's header steps aside: the page scrolls it away
  // under the pinned tabs and the frame grows upward by as much, so it stays exactly where it was. Leaving gives it back.
  let grown = $state<number | null>(null);

  async function startWork() {
    const stage = document.getElementById('stage');
    const part = shownPart();
    if (grown !== null || !stage || !part || !filling) return;
    const gap = parseFloat(getComputedStyle(part.closest('.page')!).rowGap) || 0;
    // Measured now: a bound height would still be the other layout's just after the window changes.
    grown = Math.max(0, contentTop(part, stage) - (bar?.offsetHeight ?? 0) - gap);
    await tick();
    stage.scrollTo({ top: grown, behavior: 'instant' });
  }

  // A turn that starts by any other way than the box, such as a hand-off from a lesson, counts as working too.
  let grownFor: string | null = null;
  $effect(() => {
    // The layout counts too: the header steps aside only above the tab, so a window that changes layout starts again.
    const at = app.courseOpen ? `${app.coursePart}:${filling}:${wide.current}` : null;
    const working = filling && (app.coursePart === 'sources' || studio.running);
    untrack(() => {
      if (at !== grownFor) grown = null;
      grownFor = at;
      if (working) void startWork();
    });
  });

  // One tab at a time at full height, so Studio has the room and nothing scrolls inside something else that scrolls.
  function onTabKey(event: KeyboardEvent) {
    const step = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const at = parts.findIndex((p) => p.id === app.coursePart);
    const next = parts[(at + step + parts.length) % parts.length];
    app.coursePart = next.id;
    document.getElementById(`course-tab-${next.id}`)?.focus();
  }
</script>

<article class="page still" class:filling aria-labelledby="course-title" style:--fill="{fill}px" style:--grown={grown === null ? null : `${grown}px`}>
  <!-- On a wide window the header and tabs are a column of their own beside the tab's content, so Studio and the reader
       take the window's whole height; on a narrower one they stack above it and the header steps aside as they work. -->
  <div class="side">
  <header class="head" bind:this={head}>
    <h1 id="course-title">{app.state?.course.title}</h1>
    {#if course?.goal}<p class="intro" title={course.goal}>{course.goal}</p>{/if}
    {#if imported}
      <div class="shared">
        <p>
          <span class="chip chip-plain">{t('Shared course')}</span>
          {#if builtFor?.goal}{t('Built for someone else’s goal: {goal}', { goal: builtFor.goal })}{/if}
        </p>
        {#if builtFor}
          <CodexLink class="btn btn-small" prompt={t('$throughline this course was shared with me. Ask me about my goal and background, record them as my learner profile, and say whether the route fits me. ')}>
            {t('Tell Studio your goal')}
          </CodexLink>
        {/if}
      </div>
    {/if}

    <!-- The whole route at a glance; a segment opens its chapter. -->
    <div class="glance">
      <ol class="strip" aria-label={t('Chapters')}>
        {#each strip as segment (segment.id || 'all')}
          <li style:flex-grow={Math.max(segment.total, 1)}>
            <button
              class="segment"
              class:current={current?.id === segment.id && !!segment.id && strip.length > 1}
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
        {#if current && wide.current}
          <!-- In the narrow column, which chapter and how far in it are a line each. -->
          <span class="now">
            {t('Chapter {number}', { number: currentNumber })} · {current.title}
            <span class="count">{t('{studied} of {total} sections studied', { studied: currentDone, total: current.concept_ids.length })}</span>
          </span>
        {:else if current}
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
  <div class="bar" bind:this={bar}>
    <div class="tabs" role="tablist" aria-label={t('This course')} aria-orientation={wide.current ? 'vertical' : 'horizontal'} tabindex="-1" onkeydown={onTabKey}>
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
        onfocusin={(event) => (event.target as Element).closest('.cm-editor') && void startWork()}
      >
        <Studio active={app.courseOpen && app.coursePart === 'studio'} />
      </div>
    {/if}
    </div>
    <!-- Beside Studio: its chats, as Codex lists threads beside a chat, then how the learner is taught. -->
    <div class="studio-aside">
      {#if studio.available}<StudioChats />{/if}
      <TeachingPreferences />
    </div>
    </div>
  </div>

  <!-- A document opens here rather than in the side panel, which the Overview does not have (ADR 0017); the list
       narrows to a column beside it, so another is one click away. -->
  <div class="part" id="course-sources" role="tabpanel" aria-labelledby="course-tab-sources" hidden={app.coursePart !== 'sources'} class:reading class:narrow={!reading}>
    {#if reading}
      <div class="sources-list"><SourceList page /></div>
      <div class="sources-reader"><SourceViewer page /></div>
    {:else}
      <p class="lead">{t('Every document in the course; choose one to open it in the reader.')}</p>
      <SourceList page />
    {/if}
  </div>

  <div class="part narrow" id="course-share" role="tabpanel" aria-labelledby="course-tab-share" hidden={app.coursePart !== 'share'}>
    <CourseShare active={app.courseOpen && app.coursePart === 'share'} />
  </div>

  <div class="part narrow" id="course-notes" role="tabpanel" aria-labelledby="course-tab-notes" hidden={app.coursePart !== 'notes'}>
    <p class="lead">
      {notes === 1 ? t('1 highlight, note or bookmark') : t('{count} highlights, notes and bookmarks', { count: notes })}.
      {t('Export them as one Markdown file, by chapter and section; notes with images come as a ZIP with an images folder.')}
    </p>
    <div class="actions">
      <!-- Notes are kept beside what is read, so they open in Learn's side panel. -->
      <button class="btn btn-small" onclick={() => app.openPanel('notes')}>{t('Open notes')}</button>
      <button class="btn btn-small" disabled={!notes || exporting} onclick={exportAll}>{exporting ? t('Exporting…') : t('Export notes')}</button>
    </div>
  </div>
</article>

<style>
  /* Wide, for Studio and the reader; the tabs that are lists and forms keep a reading width inside it. */
  .page {
    max-width: 88rem;
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

  .part.narrow {
    max-width: calc(var(--measure) + 20rem);
  }

  /* An open document: the list as a column beside it, each scrolling on its own within the window. */
  .part.reading {
    grid-template-columns: 17rem minmax(0, 1fr);
    gap: 1.25rem;
    height: calc(var(--fill) + var(--grown, 0px));
  }

  .sources-list {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .sources-list :global(.source-list) {
    flex: 1;
    min-height: 0;
    padding-right: 0.25rem;
  }

  .sources-reader {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
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

  /* Whether the aside fits beside Studio depends on the page's width, not the window's: the route or a narrow window
     takes from it. */
  #course-studio {
    container-type: inline-size;
  }

  @container (min-width: 54rem) {
    .studio-row {
      grid-template-columns: minmax(0, 1fr) 17rem;
    }

    /* Beside Studio, the chats and how the learner is taught keep to the frame's height and scroll on their own, so a
       long list never runs past the window's foot and drags the page with it. */
    .studio-aside {
      max-height: calc(var(--fill) + var(--grown, 0px));
      overflow-y: auto;
      overscroll-behavior: contain;
      padding-right: 0.25rem;
      scrollbar-width: thin;
    }
  }

  .studio-aside {
    display: grid;
    gap: 1.5rem;
    align-content: start;
    min-width: 0;
  }

  /* Where the aside drops below Studio, the chats are Studio's own pinned bar instead; beside it, the bar steps aside. */
  @container (max-width: 53.99rem) {
    .studio-aside :global(.chats) {
      display: none;
    }
  }

  @container (min-width: 54rem) {
    .studio-main :global(.studio > .panel-head) {
      display: none;
    }
  }

  .studio-main {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
  }

  /* A wide frame keeps the chat to one centred column at a readable width, with its box under it, as Codex does. */
  #course-studio :global(.studio > .transcript > *),
  #course-studio :global(.studio > .panel-foot) {
    width: 100%;
    max-width: 50rem;
    margin-inline: auto;
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

  .shared {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.8rem;
    align-items: center;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .shared p {
    display: flex;
    gap: 0.5rem;
    align-items: baseline;
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
    height: calc(var(--fill) + var(--grown, 0px));
    max-height: none;
    /* Scrolling past the transcript's ends never carries on into the page, which would move the frame away. */
    overscroll-behavior: contain;
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

  /* Stacked, the side column is no box of its own: the header scrolls away and the tabs stay pinned to the stage. */
  .side {
    display: contents;
  }

  /* A wide window: the course's header and its tabs as a column on the left, the open tab beside it from the top of the
     page to the window's foot. Lists and forms stand at a reading width against the column rather than adrift in the
     middle, and Studio and the reader have the height the header took. */
  @media (min-width: 70rem) {
    .page {
      grid-template-columns: 14rem minmax(0, 1fr);
      column-gap: 2.75rem;
      align-items: start;
    }

    .side {
      position: sticky;
      top: 0;
      display: grid;
      gap: 1.5rem;
      align-content: start;
    }

    .part {
      grid-column: 2;
      grid-row: 1;
    }

    h1 {
      font-size: var(--step-2);
      line-height: 1.25;
    }

    .intro {
      -webkit-line-clamp: 4;
      line-clamp: 4;
      font-size: var(--step--1);
    }

    .glance {
      gap: 0.6rem;
    }

    .facts .now {
      display: grid;
      flex-basis: 100%;
      gap: 0.1rem;
    }

    .facts .count {
      color: var(--pencil);
      font-weight: 400;
    }

    .bar {
      position: static;
      margin-top: 0;
      border-bottom: 0;
      background: none;
    }

    .tabs {
      flex-direction: column;
      gap: 0.15rem;
      width: 100%;
    }

    .tab {
      justify-content: space-between;
      margin: 0;
      padding: 0.5rem 0.75rem;
      border: 0;
      border-radius: var(--radius);
    }

    .tab:hover {
      background: var(--accent-wash);
    }

    .tab[aria-selected='true'] {
      background: var(--accent-wash);
      color: var(--accent);
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .part.reading {
      grid-template-columns: 15rem minmax(0, 1fr);
    }
  }
</style>
