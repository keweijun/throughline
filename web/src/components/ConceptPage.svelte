<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { untrack } from 'svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { Preview } from '../lib/types';
  import UnitOverview from './UnitOverview.svelte';
  import Lesson from './Lesson.svelte';
  import LessonRequest from './LessonRequest.svelte';
  import Practice from './Practice.svelte';
  import NextSection from './NextSection.svelte';
  import CodexLink from './CodexLink.svelte';
  import DrillSession from './DrillSession.svelte';
  import KeyPoints from './KeyPoints.svelte';
  import StudioIntro from './StudioIntro.svelte';

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
  // What a New lesson replaced stays to read, folded above the lesson that replaced it (ADR 0023).
  const earlier = $derived(lessons.filter((l) => app.replaced(l)));
  const current = $derived(lessons.filter((l) => !app.replaced(l)));
  // The warm-up on offer for this section (its stale prerequisites), or the one already taken while it is open.
  const warmUp = $derived(conceptId ? app.state?.review.warm_ups[conceptId] : undefined);
  // A warm-up is a short drill session (ADR 0025), shown here until the lesson starts.
  const warmUpSession = $derived((app.state?.drills ?? []).find((s) => s.kind === 'warm_up' && s.concept_id === conceptId));
  const position = $derived(app.state?.position);
  // Key points (ADR 0024) end the lesson at the learner's position and open a finished section they come back to;
  // while a lesson is being taught, the points it will rewrite wait.
  const points = $derived(app.keyPoints(conceptId));
  const teaching = $derived(!!app.openLesson(conceptId) || lessons.some((l) => l.status === 'running'));
  const explanations = $derived(app.explanationsFor(conceptId));
  const bookmarked = $derived(!!app.bookmark(conceptId));
  const chapter = $derived(app.chapterOf(conceptId));
  // Coming back after studying a section out of route order goes to where an earlier detour returns, else to where
  // the learner is now (ADR 0006).
  const comeBackTo = $derived(app.returnSection ?? app.currentId);
  // A prerequisite not studied yet is named before the learner moves here, so they choose knowingly; nothing blocks it.
  const missing = $derived((concept?.prerequisites ?? []).filter((id) => !app.studied(id)).map((id) => app.concept(id)?.title ?? id));
  // The section's goal, shown inside About this section. One that only repeats the title, or the teacher's
  // "Afterwards you can" in the same card, says nothing, so it is left out.
  const goal = $derived.by(() => {
    const text = ((isCurrent ? position?.goal : '') || concept?.objective || concept?.goal || '').trim();
    const plain = (s: string) => s.toLocaleLowerCase().replace(/[\s.:;!?·…-]+/g, ' ').trim();
    const ability = preview?.overview.origin === 'teacher' ? preview.overview.target_ability : '';
    return text && plain(text) !== plain(concept?.title ?? '') && plain(text) !== plain(ability ?? '') ? text : '';
  });
  // The question the section answers, from the teacher's overview; it stands on the card itself.
  const question = $derived(preview?.overview.origin === 'teacher' ? preview.overview.core_problem : '');

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

{#snippet chevron()}
  <svg class="chev" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5.5 8l4.5 4.5L14.5 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
{/snippet}


{#if !conceptId || !concept}
  <section class="empty">
    <h2>{t("No learning route yet")}</h2>
    <p>{t("Codex builds the route from your files. This page updates by itself when it is done.")}</p>
    {#if app.libraryCourse}
      <CodexLink class="btn btn-primary" prompt={t('$throughline build the route for the course {course}', { course: app.libraryCourse.name })}>
        {t('Build the route in Studio')}
      </CodexLink>
    {/if}
  </section>
{:else}
  <article class="page" aria-labelledby="concept-title">
    <StudioIntro />
    {#if !isCurrent}
      <div class="previewing" role="note">
        <p>
          {t("You're previewing this section. Your learning position stays at")}
          <strong>{app.concept(app.currentId)?.title}</strong>.
          {#if missing.length}{t("{section} builds on {titles}, which you have not studied yet.", { section: concept.title, titles: missing.join(', ') })}{/if}
        </p>
        <!-- Studying a section never marks the ones in between: the learner says only where to go afterwards. -->
        <div class="previewing-actions">
          {#if conceptId === comeBackTo}
            <button class="btn btn-small btn-primary" onclick={() => app.enter(conceptId)}>{t("Return to this section")}</button>
          {:else}
            <button class="btn btn-small btn-primary" onclick={() => app.enter(conceptId, true)}>
              {t("Study this, then come back to {section}", { section: app.concept(comeBackTo)?.title ?? '' })}
            </button>
            <button class="btn btn-small" onclick={() => app.enter(conceptId)}>{t("Study from here")}</button>
          {/if}
          <button class="btn btn-small btn-quiet away" onclick={() => app.view(app.currentId!)}>{t("Back to current section")}</button>
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
      <!-- One card under the title: the question the section answers, opening to its overview, goal and sources. What to
           do next is shown where it is done (the lesson's Continue, Practice, Up next), so the header does not say it. -->
      {#if preview}
        <details class="overview" open={overviewOpen} ontoggle={toggleOverview}>
          <summary>
            {#if question}
              <span class="question">{question}</span>
              <span class="more">{t("About this section")} {@render chevron()}</span>
            {:else}
              <span class="label">{t("About this section")}</span>
              {@render chevron()}
            {/if}
          </summary>
          <div class="about-body"><UnitOverview {preview} {goal} asked={!!question} /></div>
        </details>
      {:else if !previewFailed}
        <p class="overview loading" aria-busy="true">{t("Loading the section overview…")}</p>
      {/if}
      {#if isCurrent}
        {#if app.returnSection}
          <p class="detour">
            {t("After this section, you go back to {section}.", { section: app.concept(app.returnSection)?.title ?? '' })}
            <button class="btn btn-small" onclick={() => app.enter(app.returnSection!)}>{t("Go back now")}</button>
          </p>
        {/if}
        {#if position?.progress}
          <details class="left-off">
            <summary>{t("Where you left off")}</summary>
            <p>{position.progress}</p>
          </details>
        {/if}
      {/if}
    </header>

    {#if points && !isCurrent && !teaching}
      <div class="points top"><KeyPoints value={points} /></div>
    {/if}

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


    {#if lessons.length}
      <div class="lessons">
        {#if earlier.length}
          <details class="replaced">
            <summary>{t("Earlier lesson")} <span class="chip">{t("Replaced")}</span></summary>
            {#each earlier as lesson (lesson.id)}
              <Lesson turn={lesson} />
            {/each}
          </details>
        {/if}
        {#each current as lesson (lesson.id)}
          <Lesson turn={lesson} />
        {/each}
      </div>
    {:else if !isCurrent}
      {@const ahead = index - app.routeIndex(app.currentId)}
      <!-- A later section says how far off it is; the banner above offers to study it now (ADR 0006). -->
      <div class="ahead">
        <p>
          {#if ahead > 1}{t("No lesson yet. {count} sections come before it, starting with the one you're on.", { count: ahead })}
          {:else if ahead === 1}{t("No lesson yet. It comes right after the section you're on.")}
          {:else}{t("No lesson yet.")}{/if}
        </p>
        {#if chapter && chapter.id !== app.chapterOf(app.currentId)?.id}
          <div class="previewing-actions">
            <button class="btn btn-small" onclick={() => app.viewChapter(chapter.id)}>{t("Open its chapter")}</button>
          </div>
        {/if}
      </div>
    {/if}

    {#if points && isCurrent && !teaching}
      <div class="points end"><KeyPoints value={points} /></div>
    {/if}

    <!-- While a stepped lesson has steps left, Continue under its latest step is the way on. -->
    {#if isCurrent && !lessons.length}
      <!-- A warm-up on prerequisites studied a while ago, offered once and never in the way of the lesson (ADR 0014). -->
      {#if warmUpSession}
        <aside class="warm-up session" aria-label={t("Warm-up")}>
          <h2 class="warm-title">{t("Warm-up")}</h2>
          <DrillSession session={warmUpSession} />
        </aside>
      {:else if warmUp}
        <!-- Title and dismissal on top, what it is and the choice to take it on one row below. -->
        <aside class="warm-up" aria-label={t("Warm-up")}>
          <header class="warm-head">
            <h2 class="warm-title">{t("Warm-up")}</h2>
            <button class="btn btn-quiet btn-small dismiss" onclick={() => app.dismissWarmUp(conceptId)} aria-label={t("No thanks")} title={t("No thanks")}>
              <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg>
            </button>
          </header>
          <div class="warm-offer">
            <p>{t("This section builds on {sections}, which you have not practised for a while.", { sections: warmUp.map((id) => app.concept(id)?.title ?? id).join(', ') })}</p>
            <button class="btn btn-small" onclick={() => app.startDrill({ kind: 'warm_up', concept_id: conceptId! }, true)}>{t("Warm up on what this builds on")}</button>
          </div>
        </aside>
      {/if}
    {/if}

    {#if isCurrent}
      <LessonRequest conceptId={conceptId} hasLesson={app.hasLesson(conceptId)} open={!!app.openLesson(conceptId)} />
    {/if}

    <Practice conceptId={conceptId} {isCurrent} />

    {#if isCurrent}
      <NextSection conceptId={conceptId} />
    {/if}
  </article>
{/if}

<style>
  .page {
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

  /* Leaving the preview is not one of the choices about this section: it keeps to the right. */
  .away {
    margin-left: auto;
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


  .detour {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
    margin-top: 0.9rem;
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  .left-off {
    margin-top: 0.9rem;
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  .left-off summary {
    cursor: pointer;
    color: var(--accent);
    font-weight: 500;
    font-size: var(--step-0);
  }

  .left-off p {
    margin-top: 0.4rem;
  }

  /* The card under the title: the section's question, and About this section, which opens it. */
  .overview {
    margin-top: 1.25rem;
    padding: 0.85rem 1.1rem;
    border-radius: var(--radius);
    background: var(--sheet);
    border: 1px solid var(--rule);
  }

  /* One line of the page's size, as the loading line is, so the card is the same height loaded or not. */
  .overview summary {
    display: flex;
    align-items: center;
    gap: 1rem;
    min-height: 1.5em;
    font-size: var(--step-0);
    line-height: 1.5;
    cursor: pointer;
    list-style: none;
  }

  .overview summary::-webkit-details-marker {
    display: none;
  }

  /* Its own chevron, on the right, replaces the page's ▸ before a summary. */
  .overview summary::before {
    content: none;
    display: none;
  }

  .overview .question {
    flex: 1;
    min-width: 0;
    font-family: var(--serif);
    font-style: italic;
    color: var(--ink-soft);
  }

  .overview .label {
    flex: 1;
    color: var(--ink);
  }

  .overview .more {
    display: inline-flex;
    flex: none;
    align-items: center;
    gap: 0.3rem;
    color: var(--accent);
    font-size: var(--step--1);
    font-weight: 600;
  }

  .overview .chev {
    flex: none;
    color: var(--accent);
    transition: rotate var(--quick) ease;
  }

  .overview[open] .chev {
    rotate: 180deg;
  }

  .about-body {
    margin-top: 0.9rem;
    padding-top: 0.9rem;
    border-top: 1px solid var(--rule);
  }

  /* While the overview loads, the card keeps its place and size, so nothing below it moves when it arrives. */
  .overview.loading {
    color: var(--pencil);
    font-size: var(--step-0);
    line-height: 1.5;
  }

  .points.top {
    margin-bottom: 2rem;
  }

  .points.end {
    margin-top: 2.5rem;
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

  /* A lesson a New lesson replaced, kept to read: one quiet line until opened. */
  .replaced {
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--rule);
  }

  .replaced summary {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    color: var(--pencil);
    font-size: var(--step-0);
  }

  .replaced summary:hover {
    color: var(--ink);
  }

  .replaced[open] {
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

  .warm-up {
    display: grid;
    gap: 0.6rem;
    margin: 1.5rem 0 1rem;
    padding: 1rem 1rem 1.1rem 1.35rem;
    border: 1px solid var(--rule);
    border-left: 3px solid var(--marker);
    border-radius: var(--radius);
    background: var(--raised);
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  /* A warm-up under way holds question cards with accent borders of their own: no second one around them. */
  .warm-up.session {
    border-left-width: 1px;
  }

  .warm-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .warm-title {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink);
  }

  .dismiss {
    margin: -0.3rem -0.3rem -0.3rem 0;
    padding: 0.25rem;
    color: var(--pencil);
  }

  .warm-offer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem 1.25rem;
  }

  .warm-offer p {
    flex: 1 1 18rem;
    margin: 0;
  }
</style>
