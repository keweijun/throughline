<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { pop } from '../lib/motion';
  import { studio } from '../lib/studio.svelte';
  import CodexLink from './CodexLink.svelte';
  import Studio from './Studio.svelte';
  import StudioChats from './StudioChats.svelte';
  import TeachingPreferences from './TeachingPreferences.svelte';
  import CourseShare from './CourseShare.svelte';
  import CourseCover from './CourseCover.svelte';

  // The course's Studio place, the first of its three places (ADR 0017): Codex working on the course, as tall as the
  // window and no wider than a chat needs, with the course and its chats in a column beside it, as Codex lists its
  // threads. A source opens in the side panel on the right, as it does in Learn and Review.
  const course = $derived(app.libraryCourse);
  const route = $derived(app.state?.curriculum.route ?? []);
  const current = $derived(app.chapterOf(app.currentId));
  const currentNumber = $derived(app.chapters.findIndex((c) => c.id === current?.id) + 1);
  const currentDone = $derived(current ? current.concept_ids.filter((id) => app.studied(id)).length : 0);

  // One segment per chapter, as wide as its sections, filled as they are studied. A course without chapters is one.
  const strip = $derived(
    (app.chapters.length ? app.chapters : [{ id: '', title: app.state?.course.title ?? '', concept_ids: route }]).map((chapter) => {
      const done = chapter.concept_ids.filter((id) => app.studied(id)).length;
      return { id: chapter.id, title: chapter.title, total: chapter.concept_ids.length, done };
    }),
  );

  // A course started fresh from someone else's package (ADR 0020): the route was built for their goal, so the page asks
  // for the learner's own until Studio records it.
  const imported = $derived(app.state?.course.imported ?? null);
  const builtFor = $derived(app.state?.course.built_for ?? null);

  // The course's own actions beside its title, the same as on its card in the library (ADR 0022): Share… and Rename.
  // The menu and the share options float over Studio rather than inside the column, which is too narrow for them and
  // scrolls on its own, so they are placed from the button's position.
  let more = $state<HTMLElement>();
  let opened = $state<'menu' | 'share' | null>(null);
  let at = $state({ top: 0, left: 0 });
  function open(what: 'menu' | 'share') {
    const box = more?.getBoundingClientRect();
    if (box) at = { top: box.bottom + 6, left: box.left };
    opened = what;
  }
  $effect(() => {
    if (!opened) return;
    const away = (event: Event) => !(event.target as Element).closest?.('[data-course-actions]') && (opened = null);
    const escape = (event: KeyboardEvent) => event.key === 'Escape' && (opened = null);
    const close = () => (opened = null);
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', escape);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', escape);
      window.removeEventListener('resize', close);
    };
  });

  let renaming = $state(false);
  let title = $state('');
  let saving = $state(false);
  function startRename() {
    opened = null;
    title = app.state?.course.title ?? '';
    renaming = true;
    requestAnimationFrame(() => (document.getElementById('course-rename') as HTMLTextAreaElement | null)?.select());
  }
  async function rename() {
    const name = course?.name;
    if (!name || !title.trim() || saving) return;
    if (title.trim() !== app.state?.course.title) {
      saving = true;
      try {
        await api.put(`/api/library/courses/${encodeURIComponent(name)}/title`, { title });
        await app.loadLibrary(true);
      } catch (error) {
        app.error = error instanceof Error ? error.message : String(error);
        return;
      } finally {
        saving = false;
      }
    }
    renaming = false;
  }
</script>

<article class="page still filling" aria-labelledby="course-title">
  <div class="place" id="course-studio">
    <!-- The course, its chats and how the learner is taught; it folds away when a source beside Studio needs the room,
         and Studio's own chats menu comes back. -->
    <aside class="studio-aside" aria-label={t('This course')}>
      <header class="head">
        <!-- The course's cover, as on its card in the library (ADR 0027). -->
        {#if course}<div class="cover"><CourseCover {course} /></div>{/if}
        {#if renaming}
          <form class="rename" onsubmit={(event) => (event.preventDefault(), void rename())}>
            <textarea
              id="course-rename"
              aria-label={t('Course title')}
              rows="2"
              maxlength="200"
              bind:value={title}
              onkeydown={(event) => {
                if (event.key === 'Escape') renaming = false;
                else if (event.key === 'Enter' && !event.shiftKey) (event.preventDefault(), void rename());
              }}
            ></textarea>
            <div class="rename-actions">
              <button class="btn btn-small" type="submit" disabled={saving || !title.trim()}>{t('Save')}</button>
              <button class="btn btn-quiet btn-small" type="button" onclick={() => (renaming = false)}>{t('Cancel')}</button>
            </div>
          </form>
        {:else}
          <div class="title-row">
            <h1 id="course-title">{app.state?.course.title}</h1>
            {#if course}
              <button
                class="btn btn-quiet btn-small more"
                bind:this={more}
                data-course-actions
                aria-haspopup="menu"
                aria-expanded={opened === 'menu'}
                aria-label={t('More actions for {course}', { course: app.state?.course.title ?? '' })}
                onclick={() => (opened === 'menu' ? (opened = null) : open('menu'))}
              >
                <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="4.5" cy="10" r="1.5" fill="currentColor" /><circle cx="10" cy="10" r="1.5" fill="currentColor" /><circle cx="15.5" cy="10" r="1.5" fill="currentColor" /></svg>
              </button>
            {/if}
          </div>
        {/if}
        {#if course?.goal}<p class="goal" title={course.goal}>{course.goal}</p>{/if}
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
        <ol class="strip" class:many={strip.length > 12} class:crowded={strip.length > 24} aria-label={t('Chapters')}>
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
        <!-- Which chapter the learner is in; a course of one chapter is the course itself, already named above. -->
        {#if current && strip.length > 1}
          <p class="now">
            {t('Chapter {number}', { number: currentNumber })} · {current.title}
            <span>{t('{studied} of {total} sections studied', { studied: currentDone, total: current.concept_ids.length })}</span>
          </p>
        {/if}
      </header>
      {#if studio.available}<StudioChats />{/if}
      <TeachingPreferences />
    </aside>

    {#if studio.available === false}
      <!-- Where Codex cannot run Studio, its hand-offs open a Codex chat instead (ADR 0016). -->
      <section class="away" aria-labelledby="away-title">
        <h2 id="away-title">{t('Change this course')}</h2>
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
      </section>
    {:else}
      <!-- Studio scrolls inside its own frame, so its writing box stays in view. -->
      <!-- An empty chat has no sheet: the question and the box stand on the page (ADR 0027). The sheet comes with the
           chat, opening out from the middle as the box goes to its foot. -->
      <div class="sheet" class:starting={studio.starting} class:unplaced={!studio.placed}>
        <div class="paper" aria-hidden="true"></div>
        <div class="frame studio-frame" data-scroller>
          <Studio active={app.courseOpen} />
        </div>
      </div>
    {/if}
  </div>

  {#if opened === 'menu'}
    <ul class="course-menu" role="menu" data-course-actions style:top="{at.top}px" style:left="{at.left}px" transition:pop={{ from: 'above' }} aria-label={t('More actions for {course}', { course: app.state?.course.title ?? '' })}>
      <li role="none"><button role="menuitem" onclick={() => open('share')}>{t('Share…')}</button></li>
      <li role="none"><button role="menuitem" onclick={startRename}>{t('Rename')}</button></li>
    </ul>
  {:else if opened === 'share' && course}
    <div class="course-share" role="group" data-course-actions style:top="{at.top}px" style:left="{at.left}px" transition:pop={{ from: 'above' }} aria-label={t('Share “{course}”', { course: app.state?.course.title ?? '' })}>
      <CourseShare course={course.name} onclose={() => (opened = null)} />
    </div>
  {/if}
</article>

<style>
  /* As tall as the window allows; the place keeps the frame and the column to it, so nothing scrolls the page. */
  .page {
    container-type: inline-size;
    height: max(24rem, calc(100dvh - var(--topbar) - 2.6rem));
  }

  /* Studio no wider than a chat reads well, the course column beside it, the two centred together. */
  .place {
    display: grid;
    grid-template-columns: 16rem minmax(0, 46rem);
    justify-content: center;
    column-gap: 2.5rem;
    height: 100%;
  }

  .studio-aside {
    display: grid;
    /* One column no wider than the aside: nothing in it can widen it, and it scrolls only up and down. */
    grid-template-columns: minmax(0, 1fr);
    overflow-x: hidden;
    gap: 1.75rem;
    align-content: start;
    min-width: 0;
    height: 100%;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding-right: 0.25rem;
    scrollbar-width: thin;
  }

  .head {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 0.6rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.25;
  }

  .title-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: 0.25rem;
  }

  .more {
    margin-top: 0.15rem;
    padding: 0.25rem 0.35rem;
  }

  .rename {
    display: grid;
    gap: 0.4rem;
  }

  .rename textarea {
    width: 100%;
    padding: 0.2rem 0.4rem;
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    background: var(--sheet);
    color: var(--ink);
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.25;
    resize: none;
  }

  .rename-actions {
    display: flex;
    gap: 0.4rem;
  }

  /* Over Studio, from the ⋯ beside the title; the same look as the course card's menu in the library. */
  .course-menu,
  .course-share {
    position: fixed;
    z-index: 50;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: var(--shadow);
  }

  .course-menu {
    display: grid;
    min-width: 11rem;
    margin: 0;
    padding: 0.3rem;
    list-style: none;
  }

  .course-menu button {
    width: 100%;
    padding: 0.4rem 0.6rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink);
    font: inherit;
    font-size: var(--step--1);
    text-align: left;
    cursor: pointer;
  }

  .course-menu button:hover,
  .course-menu button:focus-visible {
    background: var(--accent-wash);
  }

  .course-share {
    display: grid;
    gap: 0.6rem;
    width: min(30rem, calc(100vw - 2rem));
    max-height: calc(100dvh - 6rem);
    overflow-y: auto;
    padding: 1rem 1.1rem;
  }

  /* A long goal stays four lines; the whole of it is in the tooltip. */
  .goal {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 4;
    line-clamp: 4;
    font-family: var(--serif);
    font-size: var(--step--1);
    line-height: 1.5;
    color: var(--ink-soft);
  }

  .shared {
    display: grid;
    gap: 0.5rem;
    justify-items: start;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .shared p {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem 0.5rem;
    align-items: baseline;
  }

  /* Always one line as wide as the column, however many chapters: the segments and the gaps between them give way,
     so a long course never widens the column or makes it scroll sideways. */
  .strip {
    display: flex;
    gap: 0.25rem;
    min-width: 0;
    margin: 0.15rem 0 0;
    padding: 0;
    list-style: none;
  }

  .strip li {
    flex-basis: 0;
    min-width: 0.5rem;
  }

  .strip.many {
    gap: 2px;
  }

  .strip.many li {
    min-width: 3px;
  }

  .strip.crowded {
    gap: 1px;
  }

  .strip.crowded li {
    min-width: 1px;
  }

  /* Thin segments are bars, not pills, so a part-studied one still reads as part filled. */
  .strip.many .segment {
    border-radius: 2px;
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

  .now {
    display: grid;
    gap: 0.1rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .now span {
    font-weight: 400;
    color: var(--pencil);
  }

  /* Studio is built for the side panel: the same surface and padding here keep its raised writing box and its pinned
     strip (.panel-foot, painted in --sheet) on one ground. Its frame keeps one height, which Studio fills with its box
     at the bottom, so content loading inside it never moves the box from under the learner's pointer. */
  .sheet {
    position: relative;
    min-width: 0;
    /* The frame inside scrolls, so the sheet is never taller than the place however long the chat is. */
    min-height: 0;
    height: 100%;
    /* Inside the sheet's edge, so what is pinned in the frame never paints over it. */
    padding: 1px;
  }

  /* The sheet itself, under the frame that scrolls: with an empty chat it is folded away below the question, and it
     rises to the frame's top as the chat begins. Its foot never moves, so the box always lands on it. */
  .paper {
    position: absolute;
    inset: 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
    transition: inset 320ms cubic-bezier(0.2, 0.7, 0.2, 1), opacity 200ms ease;
  }

  .starting .paper {
    inset: 40% 0 0;
    opacity: 0;
  }

  /* Until it is known whether there is a chat to open, no sheet, and none arriving in motion. */
  .unplaced .paper {
    opacity: 0;
    transition: none;
  }

  .frame {
    position: relative;
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
    overflow-y: auto;
    /* Scrolling past the transcript's ends never carries on into the page. */
    overscroll-behavior: contain;
    padding: 1.1rem 1.1rem 0;
  }

  /* The place names Studio and lists its chats beside it, so Studio's own heading and chats menu step aside. */
  .frame :global(.studio > .panel-head) {
    display: none;
  }

  .away {
    display: grid;
    gap: 0.75rem;
    align-content: start;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .lead {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  /* No room for both (a source open beside Studio, a narrow window): the course column folds away, as Codex hides its
     list of threads, and Studio's own chats menu comes back. */
  @container (max-width: 54rem) {
    .place {
      grid-template-columns: minmax(0, 46rem);
    }

    .studio-aside {
      display: none;
    }

    .frame :global(.studio > .panel-head) {
      display: grid;
    }

    .frame :global(.studio > .panel-head > .panel-bar),
    .frame :global(.studio > .panel-head > .panel-intro) {
      display: none;
    }
  }

  /* The course's cover tops its column. */
  .cover {
    height: 5rem;
    margin-bottom: 0.35rem;
    overflow: hidden;
    border: 1px solid var(--rule);
    border-radius: 10px;
  }

  .cover :global(.name) {
    font-size: 1.5rem;
  }

  /* Beside its list of chats the box need not name the chat again; it still says where a request came from. */
  .frame :global(.studio:not(.from-elsewhere) .composer .head) {
    display: none;
  }

  @media (prefers-reduced-motion: reduce) {
    .segment,
    .fill,
    .paper {
      transition: none;
    }
  }
</style>
