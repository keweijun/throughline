<script lang="ts">
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { lessonStatus } from '../lib/format';
  import type { Question } from '../lib/types';
  import TurnControls from './TurnControls.svelte';

  let { question }: { question: Question } = $props();

  const answer = $derived(app.turn(question.turn_id));
  const supplement = $derived(app.turn(question.supplement_turn_id));
  const decision = $derived(question.decision);
  const later = $derived(decision?.category === 'future' && decision.target_concept_id ? app.concept(decision.target_concept_id) : undefined);
  const scheduled = $derived(app.state?.deferred_explanations.find((e) => e.id === `web:${question.id}`));
  // Returning restores reading inside the section the question was asked from; once the route moves on there is nothing to return to.
  const canReturn = $derived(question.restore_point?.concept_id === app.currentId);
  const categories: Record<string, string> = {
    local: 'about this passage',
    prerequisite: 'a missing foundation',
    future: 'covered fully later',
    repeated: 'a repeated difficulty',
    extension: 'an extension',
  };

  let node: HTMLElement | undefined = $state();
  let flash = $state(false);

  $effect(() => {
    if (app.focusThread !== question.id || !node || !app.panelOpen) return;
    requestAnimationFrame(() => node!.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    flash = true;
    app.focusThread = null;
    const timer = setTimeout(() => (flash = false), 1600);
    return () => clearTimeout(timer);
  });

  function choose(choice: 'accept' | 'decline') {
    return app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/choice`, { choice }));
  }

  async function backToLesson() {
    const result = await app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/return`));
    if (!result) return;
    if (matchMedia('(max-width: 79.99rem)').matches) app.panelOpen = false;
    await app.returnTo(question);
  }

  function previewLater() {
    if (matchMedia('(max-width: 79.99rem)').matches) app.panelOpen = false;
    app.view(later!.id);
  }
</script>

<article class="thread" class:flash id="thread-{question.id}" bind:this={node}>
  {#if question.selection}<blockquote>{question.selection}</blockquote>{/if}
  <div class="prose title" role="heading" aria-level="4" aria-label={question.question} use:markdown={{ language: locale.language, text: question.question }}></div>

  {#if answer?.text}
    <div class="prose answer" use:markdown={{ language: locale.language, text: answer.text, refs: answer.source_refs, onSource: (r) => app.openSource(r) }}></div>
  {/if}
  {#if answer && answer.status !== 'completed'}
    <div class="state">
      <span class="chip chip-{lessonStatus[answer.status].tone}">
        {#if answer.status === 'running'}<span class="live-dot"></span>{t("Answering")}{:else}{diagnostic(lessonStatus[answer.status].label)}{/if}
      </span>
      <TurnControls turn={answer} pauseLabel={t("Pause")} regenerateLabel={t("Answer again")} />
    </div>
  {/if}

  {#if decision}
    <p class="decision">
      {decision.depth === 'short' ? t("Short answer") : t("Detailed answer")}, {diagnostic(categories[decision.category] ?? decision.category)}.
      <span>{decision.rationale}</span>
    </p>
    {#if later}
      <p class="later">
        {#if scheduled?.status === 'resolved'}
          {t("Explained in full in {section}.", { section: later.title })}
        {:else}
          {t("The full explanation is saved for {section}.", { section: later.title })}
        {/if}
        {#if later.id !== app.viewingId}
          <button class="btn btn-quiet btn-small" onclick={previewLater}>{t("Look at that section")}</button>
        {/if}
      </p>
    {/if}
  {:else if answer?.status === 'completed'}
    <p class="decision">{t("Answered. The teacher did not say how this question fits the route, so it is not scheduled for a later section.")}</p>
  {/if}

  {#if question.status === 'suggested' && decision}
    <div class="suggest">
      <p>{t("The teacher suggests studying a foundation first:")} <strong>{decision.supplement_goal}</strong>{t(". The lesson pauses while you do.")}</p>
      <div class="row">
        <button class="btn btn-small btn-primary" onclick={() => choose('accept')}>{t("Study the foundations first")}</button>
        <button class="btn btn-small" onclick={() => choose('decline')}>{t("Continue current topic")}</button>
      </div>
    </div>
  {/if}

  {#if supplement}
    <section class="supplement" aria-label={t("Foundation supplement")}>
      <p class="supplement-status">
        {t("Foundation:")} {decision?.supplement_goal}
        <span class="chip chip-{lessonStatus[supplement.status].tone}">
          {#if supplement.status === 'running'}<span class="live-dot"></span>{/if}{diagnostic(lessonStatus[supplement.status].label)}
        </span>
      </p>
      {#if supplement.text}
        <div class="prose" use:markdown={{ language: locale.language, text: supplement.text, refs: supplement.source_refs, onSource: (r) => app.openSource(r) }}></div>
      {/if}
      <TurnControls turn={supplement} pauseLabel={t("Pause supplement")} regenerateLabel={t("Regenerate supplement")} />
    </section>
  {/if}

  {#if canReturn}
    <div class="row end">
      <button class="btn btn-quiet btn-small" onclick={backToLesson}>
        {question.selection && question.selected_turn_id ? t("Back to the passage") : t("Return to the lesson")}
      </button>
    </div>
  {/if}
</article>

<style>
  .thread.flash {
    animation: flash 1.6s ease-out;
  }

  @keyframes flash {
    0%,
    30% {
      background: var(--marker-wash);
      box-shadow: 0 0 0 0.6rem var(--marker-wash);
    }
  }

  .thread {
    border-radius: 2px;
    display: grid;
    gap: 0.6rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--rule);
  }

  blockquote {
    margin: 0;
    padding: 0.3rem 0.6rem;
    border-left: 3px solid var(--marker);
    background: var(--marker-wash);
    font-family: var(--serif);
    font-size: var(--step--1);
    color: var(--ink-soft);
    max-height: 5rem;
    overflow: hidden;
  }

  .title {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .answer,
  .supplement .prose {
    font-size: var(--step-0);
    line-height: 1.65;
  }

  .state,
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
  }

  .end {
    justify-content: flex-end;
  }

  .decision {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .later {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.5rem;
    font-size: var(--step--1);
    color: var(--accent);
  }

  .later .btn {
    padding-left: 0;
  }

  .suggest {
    display: grid;
    gap: 0.5rem;
    padding: 0.7rem 0.8rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
    font-size: var(--step-0);
  }

  .supplement {
    display: grid;
    gap: 0.5rem;
    padding-left: 0.8rem;
    border-left: 2px solid var(--accent);
  }

  .supplement-status {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }
</style>
