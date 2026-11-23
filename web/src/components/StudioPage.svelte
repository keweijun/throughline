<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';
  import CodexLink from './CodexLink.svelte';
  import Studio from './Studio.svelte';
  import StudioChats from './StudioChats.svelte';
  import TeachingPreferences from './TeachingPreferences.svelte';

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
</script>

<article class="page still filling" aria-labelledby="course-title">
  <div class="place" id="course-studio">
    <!-- The course, its chats and how the learner is taught; it folds away when a source beside Studio needs the room,
         and Studio's own chats menu comes back. -->
    <aside class="studio-aside" aria-label={t('This course')}>
      <header class="head">
        <h1 id="course-title">{app.state?.course.title}</h1>
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
      <div class="frame studio-frame" data-scroller>
        <Studio active={app.courseOpen} />
      </div>
    {/if}
  </div>
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
    gap: 0.6rem;
  }

  h1 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
    line-height: 1.25;
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

  .strip {
    display: flex;
    gap: 0.25rem;
    margin: 0.15rem 0 0;
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
  .frame {
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
    overflow-y: auto;
    /* Scrolling past the transcript's ends never carries on into the page. */
    overscroll-behavior: contain;
    padding: 1.1rem 1.1rem 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
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

  @media (prefers-reduced-motion: reduce) {
    .segment,
    .fill {
      transition: none;
    }
  }
</style>
