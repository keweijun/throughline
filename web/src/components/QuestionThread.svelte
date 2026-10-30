<script lang="ts">
    import { panelCoversLesson } from '../lib/media';
  import { slide } from 'svelte/transition';
  import { highlights, annotationPassage } from '../lib/highlight';
  import { locale, t } from '../lib/i18n.svelte';

  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
    import { markdown } from '../lib/markdown';
  import { lessonStatus, questionTurnIds } from '../lib/format';
  import type { Question, QuestionReply, Turn } from '../lib/types';
  import TurnControls from './TurnControls.svelte';

  let { question, open = $bindable(false) }: { question: Question; open?: boolean } = $props();

  const answer = $derived(app.turn(question.turn_id));
  const supplement = $derived(app.turn(question.supplement_turn_id));
  const decision = $derived(question.decision);
  const later = $derived(decision?.category === 'future' && decision.target_concept_id ? app.concept(decision.target_concept_id) : undefined);
  const scheduled = $derived(app.state?.deferred_explanations.find((e) => e.id === `web:${question.id}`));
  let node: HTMLElement | undefined = $state();
  let flash = $state(false);
  let busy = $state(false);

  async function retryMissing(item: QuestionReply) {
    busy = true;
    await app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/replies`, {
      id: item.id, question: item.question, selection: item.selection,
    }));
    busy = false;
  }

  $effect(() => {
    if (app.focusThread !== question.id || !node || !app.panelOpen) return;
    open = true;
    requestAnimationFrame(() => node!.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    flash = true;
    app.focusThread = null;
    const timer = setTimeout(() => (flash = false), 1600);
    return () => clearTimeout(timer);
  });

  async function choose(choice: 'accept' | 'decline') {
    if (busy) return;
    busy = true;
    await app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/choice`, { choice }));
    busy = false;
  }

  function previewLater() {
    if (panelCoversLesson()) app.panelOpen = false;
    app.view(later!.id);
  }

  // The learner's own highlights and notes on this thread's answers.
  const threadTurns = $derived(new Set(questionTurnIds(question)));
  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.turn_id && threadTurns.has(a.turn_id)));
  const passages = (turnId: string) => mine.filter((a) => a.turn_id === turnId).map(annotationPassage);
  const noted = $derived(mine.filter((a) => a.note));

  // A long list stays scannable: each thread shows a one-line summary until it is opened.
  const summary = $derived.by((): { label: string; tone: string; live?: boolean } => {
    if (questionTurnIds(question).some((id) => app.isRunning(id))) return { label: t("Answering"), tone: 'accent', live: true };
    if (answer && answer.status !== 'completed') return { label: t(lessonStatus[answer.status].label), tone: lessonStatus[answer.status].tone };
    if (supplement && supplement.status !== 'completed') return { label: t(lessonStatus[supplement.status].label), tone: lessonStatus[supplement.status].tone };
    if (question.status === 'suggested') return { label: t("Foundation suggested"), tone: 'caution' };
    if (scheduled?.status === 'pending') return { label: t("Explanation pending"), tone: 'accent' };
    if (scheduled?.status === 'resolved') return { label: t("Explained"), tone: 'good' };
    return { label: answer ? t("Answered") : t("Not started"), tone: 'plain' };
  });
  const followUps = $derived(question.replies?.length ?? 0);
</script>

<!-- Every question the learner asks reads the same way, quote first, so a follow-up looks like the question that opened the thread. -->
{#snippet answered(turn: Turn)}
  {#if turn.text}
    <div class="prose answer" data-question-answer data-turn-id={turn.id} use:highlights={{ passages: passages(turn.id), text: turn.text }} use:markdown={{ language: locale.language, text: turn.text, refs: turn.source_refs, onSource: (r) => app.openSource(r), streaming: turn.status === 'running' }}></div>
  {/if}
  {#if turn.status !== 'completed'}
    <div class="state">
      {#if turn.status !== 'running'}<span class="chip chip-{lessonStatus[turn.status].tone}">{t(lessonStatus[turn.status].label)}</span>{/if}
      <TurnControls {turn} pauseLabel={t("Pause")} regenerateLabel={t("Answer again")} />
    </div>
  {/if}
{/snippet}

<article class="thread" class:flash class:open id="thread-{question.id}" bind:this={node} data-question-id={question.id}>
  <div class="head">
    <button
      class="toggle"
      aria-expanded={open}
      aria-controls="thread-body-{question.id}"
      aria-label={open ? t("Collapse question") : t("Expand question")}
      onclick={() => (open = !open)}
    ><span aria-hidden="true" class="chevron" class:open></span></button>
    <!-- The whole summary opens the thread; the toggle button is the keyboard-accessible control. -->
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div class="summary" onclick={() => (open = true)}>
      <div class="asked">
        {#if open && question.selection}<blockquote class="prose asked-passage" use:markdown={{ language: locale.language, text: question.selection }}></blockquote>{/if}
        <div class="prose title" role="heading" aria-level="4" aria-label={question.question} use:markdown={{ language: locale.language, text: question.question }}></div>
      </div>
      <p class="meta">
        <span class="chip chip-{summary.tone}">{#if summary.live}<span class="live-dot"></span>{/if}{summary.label}</span>
        {#if followUps}<span>{followUps === 1 ? t("1 follow-up") : t("{count} follow-ups", { count: followUps })}</span>{/if}
        {#if noted.length}
          <button class="your-notes" onclick={(e) => (e.stopPropagation(), app.showAnnotation(noted[0].id))}>
            <span aria-hidden="true">✎</span> {noted.length === 1 ? t("1 note") : t("{count} notes", { count: noted.length })}
          </button>
        {/if}
      </p>
    </div>
  </div>

  {#if open}
  <div class="body" id="thread-body-{question.id}" transition:slide={{ duration: 200 }}>
  {#if answer}{@render answered(answer)}{/if}

  <!-- How the teacher placed the question on the route is its own reasoning; the learner sees only what it changes. -->
  {#if later}
    <p class="later">
      {#if scheduled?.status === 'resolved'}
        {t("Explained in full in {section}.", { section: later.title })}
      {:else}
        {t("The full explanation is saved for {section}.", { section: later.title })}
      {/if}
      {#if later.id !== app.viewingId}
        <button class="btn btn-quiet btn-small btn-flush" onclick={previewLater}>{t("Look at that section")}</button>
      {/if}
    </p>
  {/if}

  {#if question.status === 'suggested' && decision}
    {@const [before, after] = t("The teacher suggests studying a foundation first: {goal}. The lesson pauses while you do.").split('{goal}')}
    <div class="suggest">
      <p>{before}<strong>{decision.supplement_goal}</strong>{after}</p>
      <div class="row">
        <button class="btn btn-small btn-primary" disabled={busy} onclick={() => choose('accept')}>{t("Study the foundations first")}</button>
        <button class="btn btn-small" disabled={busy} onclick={() => choose('decline')}>{t("Continue current topic")}</button>
      </div>
    </div>
  {/if}

  {#if supplement}
    <section class="supplement" aria-label={t("Foundation supplement")}>
      <p class="supplement-status">
        {t("Foundation:")} {decision?.supplement_goal}
        {#if supplement.status !== 'running' && supplement.status !== 'completed'}
          <span class="chip chip-{lessonStatus[supplement.status].tone}">{t(lessonStatus[supplement.status].label)}</span>
        {/if}
      </p>
      {#if supplement.text}
        <div class="prose" data-question-answer data-turn-id={supplement.id} use:highlights={{ passages: passages(supplement.id), text: supplement.text }} use:markdown={{ language: locale.language, text: supplement.text, refs: supplement.source_refs, onSource: (r) => app.openSource(r), streaming: supplement.status === 'running' }}></div>
      {/if}
      <TurnControls turn={supplement} pauseLabel={t("Pause supplement")} regenerateLabel={t("Regenerate supplement")} />
    </section>
  {/if}

  {#each question.replies ?? [] as item (item.id)}
    {@const turn = app.turn(item.turn_id)}
    <section class="reply">
      <div class="asked">
        {#if item.selection}<blockquote class="prose asked-passage" use:markdown={{ language: locale.language, text: item.selection }}></blockquote>{/if}
        <div class="prose title" use:markdown={{ language: locale.language, text: item.question }}></div>
      </div>
      {#if turn}
        {@render answered(turn)}
      {:else}
        <div class="state">
          <p class="decision">{t("This reply did not start. Try again.")}</p>
          <button class="btn btn-small" disabled={busy} onclick={() => retryMissing(item)}>{t("Answer again")}</button>
        </div>
      {/if}
    </section>
  {/each}

  </div>
  {/if}
</article>

<style>
  .head {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.3rem;
    align-items: start;
  }

  .toggle {
    width: 1.4rem;
    padding: 0.1rem 0;
    border: 0;
    background: none;
    color: var(--pencil);
    cursor: pointer;
  }

  .summary {
    display: grid;
    gap: 0.3rem;
    cursor: pointer;
  }

  /* Collapsed, a thread is one row of a list; open, its question reads like every follow-up below it. */
  .thread:not(.open) .asked {
    padding: 0;
    background: none;
  }

  .thread:not(.open) .title {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .body {
    display: grid;
    gap: 0.6rem;
    padding-left: 1.7rem;
  }

  .your-notes { padding: 0; border: 0; background: none; color: var(--mine); font: inherit; font-weight: 600; cursor: pointer; }

  /* An open thread keeps its question in view while its answers scroll by, clear of the panel's close button. */
  .thread.open .head {
    position: sticky;
    top: 0;
    z-index: 1;
    margin: -0.4rem 0 0;
    padding: 0.4rem 2.2rem 0.5rem 0;
    background: var(--sheet);
    box-shadow: 0 1px 0 var(--rule);
  }

  .reply {
    display: grid;
    gap: 0.6rem;
    margin-top: 1rem;
  }

  /* What the learner asked reads apart from the teacher's answers. */
  .asked {
    display: grid;
    gap: 0.4rem;
    padding: 0.55rem 0.75rem 0.6rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
  }

  /* Follow-ups keep the inset the open thread's sticky question leaves for the panel's close button, so every question box lines up. */
  .reply .asked {
    margin-right: 2.2rem;
  }

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
    padding-bottom: 0.8rem;
    border-bottom: 1px solid var(--rule);
  }


  /* An open thread's question stays in view, so its quote is kept short there; scroll it to read the rest. */
  .head blockquote {
    max-height: 4.6em;
  }

  .title {
    font-family: var(--sans);
    font-size: var(--step-0);
    font-weight: 600;
    line-height: 1.45;
  }

  .answer,
  .supplement .prose {
    font-size: var(--step-0);
    line-height: 1.65;
  }

  /* An answer's headings organise it; they should not outrank the question it answers. */
  .answer :global(h1),
  .answer :global(h2),
  .supplement .prose :global(h1),
  .supplement .prose :global(h2) {
    font-size: var(--step-1);
  }

  .answer :global(h3),
  .answer :global(h4),
  .supplement .prose :global(h3),
  .supplement .prose :global(h4) {
    font-size: var(--step-0);
  }

  .state,
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
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
