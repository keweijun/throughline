<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { Preview } from '../lib/types';
  import UnitOverview from './UnitOverview.svelte';
  import Lesson from './Lesson.svelte';
  import Composer from './Composer.svelte';
  import Practice from './Practice.svelte';
  import NextSection from './NextSection.svelte';
  import Preparation from './Preparation.svelte';
  import EarlierHistory from './EarlierHistory.svelte';

  let { conceptId }: { conceptId: string | null } = $props();

  let preview = $state<Preview | null>(null);
  let overviewOpen = $state(false);

  const concept = $derived(app.concept(conceptId));
  const index = $derived(app.routeIndex(conceptId));
  const total = $derived(app.state?.curriculum.route.length ?? 0);
  const isCurrent = $derived(conceptId === app.currentId);
  const lessons = $derived(app.lessons(conceptId));
  const position = $derived(app.state?.position);
  const seenKey = $derived(`overview-seen:${app.state?.course.id}:${conceptId}`);

  onMount(async () => {
    if (!conceptId) return;
    let seen = false;
    try {
      seen = !!localStorage.getItem(seenKey);
    } catch {
      seen = false;
    }
    overviewOpen = !app.hasLesson(conceptId) && !seen;
    try {
      preview = await api.get<Preview>(`/api/concepts/${encodeURIComponent(conceptId)}/preview`);
    } catch (e) {
      app.error = (e as Error).message;
    }
  });

  function toggleOverview(event: Event) {
    overviewOpen = (event.currentTarget as HTMLDetailsElement).open;
    if (!overviewOpen) {
      try {
        localStorage.setItem(seenKey, 'seen');
      } catch {
        // Only affects whether the overview opens next time.
      }
    }
  }
</script>

{#if !conceptId || !concept}
  <section class="empty">
    <h2>{t("No learning route yet")}</h2>
    <p>{t("Plan a course route with the guided-learning skill, then reopen this page to start the first section.")}</p>
  </section>
{:else}
  <article class="page" aria-labelledby="concept-title">
    {#if !isCurrent}
      <div class="previewing" role="note">
        <p>
          {t("You're previewing this section. Your learning position stays at")}
          <strong>{app.concept(app.currentId)?.title}</strong>.
        </p>
        <button class="btn btn-small" onclick={() => app.view(app.currentId!)}>{t("Back to current section")}</button>
      </div>
    {/if}

    <header class="head">
      <p class="eyebrow">{t('Section {number} of {total}', { number: index + 1, total })}</p>
      <h1 id="concept-title">{concept.title}</h1>
      {#if isCurrent && position}
        <dl class="position">
          <div>
            <dt>{t("Goal")}</dt>
            <dd>{position.goal || preview?.overview.target_ability || t("Read the lesson, then try the exercises")}</dd>
          </div>
          <div>
            <dt>{t("Next step")}</dt>
            <dd>{position.next_step || t("Read the lesson, then try the exercises")}</dd>
          </div>
        </dl>
        {#if position.progress}
          <details class="left-off">
            <summary>{t("Where you left off")}</summary>
            <p>{position.progress}</p>
          </details>
        {/if}
      {/if}
    </header>

    {#if preview}
      <details class="overview" open={overviewOpen} ontoggle={toggleOverview}>
        <summary>
          {preview.overview.origin === 'teacher' ? t("Unit overview") : t("Route and sources")}
        </summary>
        <UnitOverview {preview} />
      </details>
    {/if}

    {#if lessons.length}
      <div class="lessons">
        {#each lessons as lesson (lesson.id)}
          <Lesson turn={lesson} />
        {/each}
      </div>
    {:else if !isCurrent}
      <p class="quiet">{t("No lesson yet. This section starts when you reach it on the route.")}</p>
    {/if}

    {#if isCurrent}
      <Composer conceptId={conceptId} hasLesson={app.hasLesson(conceptId)} />
    {/if}

    <Practice conceptId={conceptId} {isCurrent} />

    {#if isCurrent}
      <NextSection conceptId={conceptId} />
      <Preparation />
      <EarlierHistory />
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

  .lessons {
    display: grid;
    gap: 2.5rem;
  }

  .quiet {
    color: var(--pencil);
    font-size: var(--step-0);
  }

  @media (max-width: 40rem) {
    .position {
      grid-template-columns: 1fr;
      gap: 0.75rem;
    }
  }
</style>
