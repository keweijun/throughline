<script lang="ts">
  import { highlights } from '../lib/highlight';
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { autogrow } from '../lib/autogrow';
  import { markdown } from '../lib/markdown';
  import { lessonStatus } from '../lib/format';
  import type { Question, QuestionReply } from '../lib/types';
  import TurnControls from './TurnControls.svelte';

  let { question, open = $bindable(false) }: { question: Question; open?: boolean } = $props();

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
  let replyText = $state('');
  let busy = $state(false);
  const quote = $derived(app.quote?.questionId === question.id ? app.quote : null);
  const canReply = $derived(answer?.status === 'completed' && (!supplement || supplement.status === 'completed') && (question.replies ?? []).every((r) => app.turn(r.turn_id)?.status === 'completed'));

  async function retryMissing(item: QuestionReply) {
    busy = true;
    await app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/replies`, {
      id: item.id, question: item.question, selection: item.selection,
    }));
    busy = false;
  }

  async function reply(event: SubmitEvent) {
    event.preventDefault();
    if (!replyText.trim() || !canReply || busy) return;
    busy = true;
    const result = await app.act(() => api.post(`/api/questions/${encodeURIComponent(question.id)}/replies`, {
      id: newId(), question: replyText, selection: quote?.text ?? '',
    }));
    busy = false;
    if (result) { replyText = ''; if (quote) app.quote = null; }
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

  // The learner's own highlights and notes on this thread's answers.
  const threadTurns = $derived(new Set([question.turn_id, question.supplement_turn_id, ...(question.replies ?? []).map((r) => r.turn_id)]));
  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.turn_id && threadTurns.has(a.turn_id)));
  const passages = (turnId: string) => mine.filter((a) => a.turn_id === turnId).map((a) => a.passage);
  const noted = $derived(mine.filter((a) => a.note));

  // A long list stays scannable: each thread shows a one-line summary until it is opened.
  const section = $derived(app.concept(question.anchor?.concept_id ?? question.restore_point?.concept_id));
  const summary = $derived.by((): { label: string; tone: string; live?: boolean } => {
    const busy = [answer, supplement, ...(question.replies ?? []).map((r) => app.turn(r.turn_id))].find((x) => x?.status === 'running');
    if (busy) return { label: t("Answering"), tone: 'accent', live: true };
    if (answer && answer.status !== 'completed') return { label: diagnostic(lessonStatus[answer.status].label), tone: lessonStatus[answer.status].tone };
    if (question.status === 'suggested') return { label: t("Foundation suggested"), tone: 'caution' };
    if (scheduled?.status === 'pending') return { label: t("Explanation pending"), tone: 'accent' };
    if (scheduled?.status === 'resolved') return { label: t("Explained"), tone: 'good' };
    return { label: answer ? t("Answered") : t("Not started"), tone: 'plain' };
  });
  const followUps = $derived(question.replies?.length ?? 0);
</script>

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
      <div class="prose title" role="heading" aria-level="4" aria-label={question.question} use:markdown={{ language: locale.language, text: question.question }}></div>
      <p class="meta">
        <span class="chip chip-{summary.tone}">{#if summary.live}<span class="live-dot"></span>{/if}{summary.label}</span>
        {#if section}<span>{section.title}</span>{/if}
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
  <div class="body" id="thread-body-{question.id}">
  {#if question.selection}<blockquote class="prose" use:markdown={{ language: locale.language, text: question.selection }}></blockquote>{/if}
  {#if answer?.text}
    <div class="prose answer" data-question-answer data-turn-id={answer.id} use:highlights={{ passages: passages(answer.id), text: answer.text }} use:markdown={{ language: locale.language, text: answer.text, refs: answer.source_refs, onSource: (r) => app.openSource(r) }}></div>
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
        <div class="prose" data-question-answer data-turn-id={supplement.id} use:highlights={{ passages: passages(supplement.id), text: supplement.text }} use:markdown={{ language: locale.language, text: supplement.text, refs: supplement.source_refs, onSource: (r) => app.openSource(r) }}></div>
      {/if}
      <TurnControls turn={supplement} pauseLabel={t("Pause supplement")} regenerateLabel={t("Regenerate supplement")} />
    </section>
  {/if}

  {#each question.replies ?? [] as item (item.id)}
    {@const turn = app.turn(item.turn_id)}
    <section class="reply">
      {#if item.selection}<blockquote class="prose" use:markdown={{ language: locale.language, text: item.selection }}></blockquote>{/if}
      <div class="prose title" use:markdown={{ language: locale.language, text: item.question }}></div>
      {#if turn}
        <div class="prose answer" data-question-answer data-turn-id={turn.id} use:highlights={{ passages: passages(turn.id), text: turn.text }} use:markdown={{ language: locale.language, text: turn.text, refs: turn.source_refs, onSource: (r) => app.openSource(r) }}></div>
        {#if turn.status !== 'completed'}
          <span class="chip">{diagnostic(lessonStatus[turn.status].label)}</span>
          <TurnControls {turn} pauseLabel={t("Pause")} regenerateLabel={t("Answer again")} />
        {/if}
      {:else}
        <p class="decision">{t("This reply did not start. Try again.")}</p>
        <button class="btn btn-small" disabled={busy} onclick={() => retryMissing(item)}>{t("Answer again")}</button>
      {/if}
    </section>
  {/each}

  <form class="followup" onsubmit={reply}>
    {#if quote}
      <blockquote class="prose" use:markdown={{ language: locale.language, text: quote.text }}></blockquote>
      <button type="button" class="btn btn-quiet btn-small" onclick={() => (app.quote = null)}>{t("Remove quote")}</button>
    {/if}
    <label class="field">
      <span>{t("Follow up")}</span>
      <textarea id="reply-input-{question.id}" rows="2" bind:value={replyText} use:autogrow={replyText} aria-label={t("Follow-up question")} placeholder={t("Continue this question…")}></textarea>
    </label>
    <button class="btn btn-small" disabled={busy || !canReply || !replyText.trim()}>{t("Send follow-up")}</button>
  </form>

  {#if canReturn}
    <div class="row end">
      <button class="btn btn-quiet btn-small" onclick={backToLesson}>
        {question.selection && question.selected_turn_id ? t("Back to the passage") : t("Return to the lesson")}
      </button>
    </div>
  {/if}
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
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    gap: 0.6rem;
    padding-left: 1.7rem;
  }

  .your-notes { padding: 0; border: 0; background: none; color: var(--mine); font: inherit; font-weight: 600; cursor: pointer; }
  .reply { border-top: 1px solid var(--rule); padding-top: 1rem; display: grid; gap: 0.6rem; }
  .followup { display: grid; gap: 0.5rem; margin-top: 0.75rem; }
  .followup > button { justify-self: start; }

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

  blockquote {
    margin: 0;
    padding: 0.3rem 0.6rem;
    border-left: 3px solid var(--marker);
    background: var(--marker-wash);
    font-family: var(--serif);
    font-size: var(--step--1);
    color: var(--ink-soft);
    max-height: 8rem;
    overflow: auto;
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
