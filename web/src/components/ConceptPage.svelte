<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { untrack } from 'svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { open as isOpen } from '../lib/format';
  import type { Preview } from '../lib/types';
  import UnitOverview from './UnitOverview.svelte';
  import Lesson from './Lesson.svelte';
  import Composer from './Composer.svelte';
  import Practice from './Practice.svelte';
  import NextSection from './NextSection.svelte';
  import EarlierHistory from './EarlierHistory.svelte';
  import CodexLink from './CodexLink.svelte';

  let { conceptId }: { conceptId: string | null } = $props();

  let preview = $state<Preview | null>(null);
  let previewFailed = $state(false);
  // The overview is a reference the learner opens; the teacher's first lesson opens the chapter with its own.
  let overviewOpen = $state(false);

  const concept = $derived(app.concept(conceptId));
  const index = $derived(app.routeIndex(conceptId));
  const total = $derived(app.state?.curriculum.route.length ?? 0);
  const isCurrent = $derived(conceptId === app.currentId);
  const lessons = $derived(app.lessons(conceptId));
  const position = $derived(app.state?.position);
  const explanations = $derived(app.explanationsFor(conceptId));
  const bookmarked = $derived(!!app.bookmark(conceptId));
  const chapter = $derived(app.chapterOf(conceptId));
  const skipped = $derived(app.isSkipped(conceptId));
  const goal = $derived(
    position?.goal ||
      concept?.objective ||
      concept?.goal ||
      (preview?.overview.origin === 'teacher' ? preview.overview.target_ability : t("Read the lesson, then try the exercises")),
  );

  // The host records where a section starts; what to do next follows from the lessons and practice so far.
  const nextStep = $derived.by(() => {
    if (lessons.some((l) => l.status === 'running')) return t("Follow the lesson as it is written. Select any passage to ask about it.");
    const stepped = app.openLesson(conceptId);
    if (stepped) {
      const latest = app.turn(stepped.steps.filter((s) => s.turn_id).at(-1)?.turn_id);
      return latest?.status === 'completed' ? t("Continue with the next step when you are ready.") : t("Regenerate the unfinished step to go on.");
    }
    if (!lessons.some((l) => l.status === 'completed')) return t("Regenerate the unfinished lesson, or start a new one.");
    const generating = (app.state?.practice.jobs ?? []).some((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose && !j.processed);
    if (generating) return t("Exercises are being prepared from this lesson.");
    const open = app.tasks(conceptId).filter(isOpen).length;
    const last = index === total - 1;
    if (open === 1) return last ? t("Try the open exercise below.") : t("Try the open exercise below, or enter the next section.");
    if (open) return last ? t("Try the {count} open exercises below.", { count: open }) : t("Try the {count} open exercises below, or enter the next section.", { count: open });
    return last ? t("Review this section. It is the last one on the route.") : t("Enter the next section when you are ready.");
  });

  function openQuestion(id: string) {
    app.focusThread = id.replace(/^web:/, '');
    app.openPanel('questions');
  }

  // The preview follows the course plan and its sources, so fetch it again when Codex changes them. Only the newest
  // reply counts, and none after this page has gone. The section is read through the version too: the prop reads the
  // store, so reading it directly would fetch again after every state reload.
  const planVersion = $derived(
    JSON.stringify([conceptId, app.state?.curriculum.version, app.state?.sources, app.state?.preferences.language]),
  );
  $effect(() => {
    void planVersion;
    const id = untrack(() => conceptId);
    if (!id) return;
    let current = true;
    untrack(async () => {
      try {
        const reply = await api.get<Preview>(`/api/concepts/${encodeURIComponent(id)}/preview`);
        if (!current) return;
        preview = reply;
        previewFailed = false;
      } catch (e) {
        if (!current) return;
        previewFailed = true;
        app.error = (e as Error).message;
      }
    });
    return () => (current = false);
  });


  function toggleOverview(event: Event) {
    overviewOpen = (event.currentTarget as HTMLDetailsElement).open;
  }
</script>

{#if !conceptId || !concept}
  <section class="empty">
    <h2>{t("No learning route yet")}</h2>
    <p>{t("Codex builds the route from your files. This page updates by itself when it is done.")}</p>
    {#if app.libraryCourse}
      <CodexLink class="btn btn-primary" prompt={t('$throughline build the route for the course {course}', { course: app.libraryCourse.name })}>
        {t('Build the route in Codex')}
      </CodexLink>
    {/if}
  </section>
{:else}
  <article class="page" aria-labelledby="concept-title">
    {#if !isCurrent}
      <div class="previewing" role="note">
        <p>
          {#if skipped}{t("You skipped this section with its chapter.")}{/if}
          {t("You're previewing this section. Your learning position stays at")}
          <strong>{app.concept(app.currentId)?.title}</strong>.
        </p>
        <div class="previewing-actions">
          {#if skipped}
            <button class="btn btn-small btn-primary" onclick={() => app.studySkipped(conceptId)}>{t("Study this section now")}</button>
          {/if}
          <button class="btn btn-small" onclick={() => app.view(app.currentId!)}>{t("Back to current section")}</button>
        </div>
      </div>
    {/if}

    <header class="head">
      <div class="eyebrow-row">
        {#if chapter && app.chapters.length > 1}
          <p class="eyebrow">
            <button class="chapter-link" onclick={() => app.viewChapter(chapter.id)}>{chapter.title}</button>
            · {t('Section {number} of {total}', { number: chapter.concept_ids.indexOf(conceptId) + 1, total: chapter.concept_ids.length })}
          </p>
        {:else}
          <p class="eyebrow">{t('Section {number} of {total}', { number: index + 1, total })}</p>
        {/if}
        <button
          class="btn btn-quiet btn-small bookmark"
          aria-pressed={bookmarked}
          onclick={() => app.toggleBookmark(concept.id)}
          title={t("Bookmarks are yours. The teacher does not see them.")}
        >
          <span aria-hidden="true">{bookmarked ? '★' : '☆'}</span>
          {bookmarked ? t("Bookmarked") : t("Bookmark section")}
        </button>
      </div>
      <h1 id="concept-title">{concept.title}</h1>
      {#if isCurrent}
        <dl class="position">
          <div>
            <dt>{t("Goal")}</dt>
            <dd>{goal}</dd>
          </div>
          <!-- Before the first lesson, the Start card below says what comes next. -->
          {#if lessons.length}
            <div>
              <dt>{t("Next step")}</dt>
              <dd id="next-step">{nextStep}</dd>
            </div>
          {/if}
        </dl>
        {#if position?.progress}
          <details class="left-off">
            <summary>{t("Where you left off")}</summary>
            <p>{position.progress}</p>
          </details>
        {/if}
      {/if}
    </header>

    {#if explanations.length}
      <section class="saved" aria-labelledby="saved-title">
        <h2 id="saved-title">{t("Saved for this section")}</h2>
        <p class="note">
          {#if explanations.some((e) => e.status === 'pending')}
            {t("You asked these earlier and got a short answer. The full explanation is part of this section's lesson.")}
          {:else}
            {t("Questions from earlier sections that this section's lesson explained in full.")}
          {/if}
        </p>
        <ul>
          {#each explanations as item (item.id)}
            <li>
              <span class="chip chip-{item.status === 'pending' ? 'accent' : 'good'}">
                {item.status === 'pending' ? t("Explanation pending") : t("Explained")}
              </span>
              <span class="question">{item.question}</span>
              {#if item.id.startsWith('web:')}
                <button class="btn btn-quiet btn-small" onclick={() => openQuestion(item.id)}>{t("Open question")}</button>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/if}

    {#if preview}
      <details class="overview" open={overviewOpen} ontoggle={toggleOverview}>
        <summary>
          {t("About this section")}
          {#if preview.overview.origin === 'teacher' && preview.overview.core_problem && !overviewOpen}
            <span class="teaser">{preview.overview.core_problem}</span>
          {/if}
        </summary>
        <UnitOverview {preview} />
      </details>
    {:else if !previewFailed}
      <p class="overview loading" aria-busy="true">{t("Loading the section overview…")}</p>
    {/if}

    {#if lessons.length}
      <div class="lessons">
        {#each lessons as lesson (lesson.id)}
          <Lesson turn={lesson} />
        {/each}
      </div>
    {:else if !isCurrent}
      {@const ahead = index - app.routeIndex(app.currentId)}
      <!-- The route is studied in order (ADR 0006), so a later section says how far off it is; the note above leads back. -->
      <div class="ahead">
        <p>
          {#if ahead > 1}{t("No lesson yet. You'll reach this section after {count} more on the route.", { count: ahead - 1 })}
          {:else if ahead === 1}{t("No lesson yet. This is the next section after the one you're on.")}
          {:else}{t("No lesson yet.")}{/if}
        </p>
        {#if chapter && chapter.id !== app.chapterOf(app.currentId)?.id}
          <button class="btn btn-small" onclick={() => app.viewChapter(chapter.id)}>{t("Open its chapter")}</button>
        {/if}
      </div>
    {/if}

    <!-- While a stepped lesson has steps left, Continue under its latest step is the way on. -->
    {#if isCurrent && !app.openLesson(conceptId)}
      <Composer conceptId={conceptId} hasLesson={app.hasLesson(conceptId)} />
    {/if}

    <Practice conceptId={conceptId} {isCurrent} />

    {#if isCurrent}
      <NextSection conceptId={conceptId} />
      <EarlierHistory />
    {/if}
  </article>
{/if}

<style>
  .page {
    animation: enter-rise 0.28s var(--ease-out);
    max-width: var(--measure);
    margin-inline: auto;
  }

  .empty {
    max-width: var(--measure);
    margin: 4rem auto;
    color: var(--pencil);
  }

  .empty h2 {
    font-family: var(--serif);
    font-size: var(--step-3);
    color: var(--ink);
    margin-bottom: 0.5rem;
  }

  .previewing {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 2rem;
    padding: 0.7rem 0.9rem;
    border: 1px dashed var(--rule-strong);
    border-radius: var(--radius);
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  .head {
    margin-bottom: 1.75rem;
  }

  .eyebrow-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .bookmark {
    color: var(--pencil);
  }

  .chapter-link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
  }

  .chapter-link:hover {
    text-decoration: underline;
  }

  .previewing-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .bookmark[aria-pressed='true'] {
    color: var(--mine);
    font-weight: 600;
  }

  .eyebrow {
    font-size: var(--step--1);
    color: var(--pencil);
    font-variant-numeric: tabular-nums;
  }

  h1 {
    margin-top: 0.35rem;
    font-family: var(--serif);
    font-size: clamp(var(--step-3), 4.2vw, 2.75rem);
    font-weight: 600;
    font-optical-sizing: auto;
    line-height: 1.1;
    letter-spacing: -0.012em;
    text-wrap: balance;
  }

  .position {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
    margin: 1.5rem 0 0;
    padding-top: 1rem;
    border-top: 1px solid var(--rule);
  }

  .position dt {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .position dd {
    margin: 0.2rem 0 0;
    font-size: var(--step-0);
    color: var(--ink);
  }

  .left-off {
    margin-top: 0.9rem;
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  .left-off summary,
  .overview summary {
    cursor: pointer;
    color: var(--accent);
    font-weight: 500;
    font-size: var(--step-0);
  }

  .left-off p {
    margin-top: 0.4rem;
  }

  .overview {
    margin-bottom: 2rem;
    padding: 0.85rem 1.1rem;
    border-radius: var(--radius);
    background: var(--sheet);
    border: 1px solid var(--rule);
  }

  .overview[open] summary {
    margin-bottom: 0.9rem;
  }

  .teaser {
    margin-left: 0.4rem;
    font-family: var(--serif);
    font-style: italic;
    font-weight: 400;
    color: var(--ink-soft);
  }

  .overview.loading {
    color: var(--pencil);
    font-size: var(--step-0);
  }

  .saved {
    margin-bottom: 2rem;
    padding: 0.85rem 1.1rem;
    border-radius: var(--radius);
    border: 1px solid var(--rule);
    border-left: 3px solid var(--accent);
  }

  .saved h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .saved .note {
    margin-top: 0.2rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .saved ul {
    margin: 0.6rem 0 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.4rem;
  }

  .saved li {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem;
    font-size: var(--step-0);
  }

  .saved .question {
    flex: 1 1 14rem;
  }

  .lessons {
    display: grid;
    gap: 2.5rem;
  }

  .ahead {
    display: grid;
    gap: 0.75rem;
    justify-items: start;
    color: var(--ink-soft);
    font-size: var(--step-0);
  }

  @media (max-width: 40rem) {
    .position {
      grid-template-columns: 1fr;
      gap: 0.75rem;
    }
  }
</style>
