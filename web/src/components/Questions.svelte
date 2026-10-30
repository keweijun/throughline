<script lang="ts">
  import { slide } from 'svelte/transition';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { panelCoversLesson } from '../lib/media';
  import { stageScroll } from '../lib/stage';
  import { questionTurnIds } from '../lib/format';

  import PanelComposer from './PanelComposer.svelte';
  import QuestionThread from './QuestionThread.svelte';
  import type { Question } from '../lib/types';

  let pause = $state(false);
  let busy = $state(false);

  // Oldest first, like a conversation: a new question appears just above the box it was typed in.
  const questions = $derived([...(app.state?.questions ?? [])].sort((a, b) => (a.created_at ?? app.turn(a.turn_id)?.started_at ?? 0) - (b.created_at ?? app.turn(b.turn_id)?.started_at ?? 0)));
  const currentLesson = $derived(app.lessons(app.currentId).at(-1));

  // Many questions: show this section's by default, searchable, collapsed to one line each.
  let scope = $state<'section' | 'all'>('section');
  let scopeChosen = false;
  let search = $state('');
  // One thread is open at a time, so the list stays a list and the open question stays pinned above its answers.
  let openId = $state<string | null>(null);
  const sectionOf = (q: Question) => q.anchor?.concept_id ?? q.restore_point?.concept_id;
  const inSection = $derived(questions.filter((q) => sectionOf(q) === app.viewingId));
  // Until the learner picks a scope, follow what is useful: this section if it has questions, otherwise all.
  $effect(() => {
    if (!scopeChosen) scope = inSection.length ? 'section' : 'all';
  });
  const turnsOf = (q: Question) => questionTurnIds(q).map((id) => app.turn(id));
  // A question needs the learner while it is answered, waits on a choice, or has an unfinished foundation supplement, which blocks moving on.
  const active = (q: Question) => {
    const supplement = app.turn(q.supplement_turn_id);
    return q.status === 'suggested' || questionTurnIds(q).some((id) => app.isRunning(id)) || (!!supplement && supplement.status !== 'completed');
  };
  // A question just asked or needing the learner opens by itself once.
  const autoOpened = new Set<string>();
  $effect(() => {
    for (const q of questions) {
      if (autoOpened.has(q.id) || !active(q)) continue;
      autoOpened.add(q.id);
      openId = q.id;
    }
  });
  const shown = $derived.by(() => {
    const words = search.toLowerCase().split(/\s+/).filter(Boolean);
    const pool = scope === 'section' && !words.length ? inSection : questions;
    if (!words.length) return pool;
    return pool.filter((q) => {
      const text = [q.question, q.selection, ...(q.replies ?? []).map((r) => r.question), ...turnsOf(q).map((x) => x?.text ?? '')].join(' ').toLowerCase();
      return words.every((w) => text.includes(w));
    });
  });

  // Opening a thread from elsewhere (a margin marker, a saved explanation) must find it whatever the filters say.
  $effect(() => {
    const id = app.focusThread;
    if (!id) return;
    const target = questions.find((q) => q.id === id);
    if (!target) return;
    if (!shown.includes(target)) {
      search = '';
      if (sectionOf(target) !== app.viewingId) {
        scope = 'all';
        scopeChosen = true;
      }
    }
  });

  // The box at the bottom follows up on the open thread, or asks a new question when none is open.
  const thread = $derived(questions.find((q) => q.id === openId));
  // A passage chosen in a lesson starts a new question; one chosen in an answer follows up on that answer's thread.
  $effect(() => {
    const quote = app.quote;
    if (quote) openId = quote.questionId ?? null;
  });
  const quote = $derived(app.quote && (app.quote.questionId ?? null) === (thread?.id ?? null) ? app.quote : null);

  function setOpen(q: Question, value: boolean) {
    if (value) openId = q.id;
    else if (openId === q.id) openId = null;
    // A quote waits for the box it was taken for; switching threads leaves it behind.
    if (app.quote && (app.quote.questionId ?? null) !== openId) app.quote = null;
  }

  const draftKey = $derived(thread ? `followup:${thread.id}` : 'question');
  const draft = $derived(app.drafts.get(draftKey));
  // A follow-up waits until every earlier answer in its thread has finished.
  const canReply = $derived(!thread || (
    app.turn(thread.turn_id)?.status === 'completed'
    && [thread.supplement_turn_id, ...(thread.replies ?? []).map((r) => r.turn_id)].every((id) => !id || app.turn(id)?.status === 'completed')
  ));

  async function send() {
    if (busy) return;
    busy = true;
    const text = draft;
    const key = draftKey;
    const target = thread;
    const id = newId();
    const result = await app.act(() => target
      ? api.post(`/api/questions/${encodeURIComponent(target.id)}/replies`, { id, question: text, selection: quote?.text ?? '' })
      : api.post('/api/questions', {
          id,
          question: text,
          selection: quote ? (quote.source ? `${quote.text}\n(${quote.source})` : quote.text) : '',
          selected_turn_id: quote?.turnId ?? null,
          main_turn_id: currentLesson?.id ?? null,
          anchor: { scroll_y: quote?.scrollY ?? stageScroll(), concept_id: app.viewingId },
          pause,
        }),
    );
    busy = false;
    if (!result) return;
    if (app.drafts.get(key) === text) app.drafts.set(key, '');
    if (quote) app.quote = null;
    if (!target) {
      pause = false;
      openId = id;
      app.focusThread = id;
    }
  }

  // Returning restores reading inside the section the question was asked from; once the route moves on there is nothing to return to.
  const canReturn = $derived(!!thread && thread.restore_point?.concept_id === app.currentId);

  async function backToLesson() {
    const target = thread;
    if (busy || !target) return;
    busy = true;
    const result = await app.act(() => api.post(`/api/questions/${encodeURIComponent(target.id)}/return`));
    busy = false;
    if (!result) return;
    if (panelCoversLesson()) app.panelOpen = false;
    await app.returnTo(target);
  }
</script>

<section id="branch-panel" class="panel-view" aria-labelledby="questions-title">
  <header class="panel-head">
    <div class="panel-bar">
      <h2 id="questions-title">{t("Your questions")}</h2>
      {#if questions.length}
        <div class="segmented" role="radiogroup" aria-label={t("Show questions from")} onchange={() => (scopeChosen = true)}>
          <label><input type="radio" bind:group={scope} value="section" />{t("This section ({count})", { count: inSection.length })}</label>
          <label><input type="radio" bind:group={scope} value="all" />{t("All ({count})", { count: questions.length })}</label>
        </div>
      {/if}
    </div>
    <p class="panel-intro">{t("Select a sentence or formula in a lesson or the source reader to ask about it. The lesson keeps going unless you pause it.")}</p>
    {#if questions.length > 4}
      <div class="panel-tools">
        <input type="search" bind:value={search} aria-label={t("Search questions")} placeholder={t("Search questions and answers…")} />
      </div>
    {/if}
  </header>

  <div class="panel-list">
    {#each shown as q (q.id)}
      <div transition:slide={{ duration: 200 }}>
        <QuestionThread question={q} bind:open={() => openId === q.id, (value) => setOpen(q, value)} />
      </div>
    {:else}
      <p class="panel-empty">
        {#if search.trim()}{t("No questions match your search.")}
        {:else if questions.length}{t("No questions from this section yet.")}
        {:else}{t("No questions yet.")}{/if}
      </p>
    {/each}
  </div>

  {#snippet following()}
    {t("Following up on:")} <span class="target-title" use:markdown={{ language: locale.language, text: thread!.question }}></span>
  {/snippet}
  {#snippet options()}
    {#if thread}
      {#if canReturn}
        <button type="button" class="btn btn-quiet btn-small btn-flush back" disabled={busy} onclick={backToLesson}>
          ← {thread.selection && thread.selected_turn_id ? t("Back to the passage") : t("Return to the lesson")}
        </button>
      {/if}
    {:else if app.runningLesson}
      <label class="check"><input type="checkbox" bind:checked={pause} /> {t("Pause the lesson while I ask")}</label>
    {/if}
  {/snippet}
  <PanelComposer
    id="question-input"
    value={draft}
    onvalue={(value) => app.drafts.set(draftKey, value)}
    label={thread ? t("Follow-up question") : t("Side question")}
    placeholder={thread ? t("Ask a follow-up about this…") : quote ? t("What would you like explained about this passage?") : t("What would you like explained?")}
    submitLabel={thread ? t("Send follow-up") : t("Ask")}
    disabled={busy || !canReply}
    onsubmit={send}
    context={thread ? following : undefined}
    onclear={() => thread && setOpen(thread, false)}
    clearLabel={t("Ask a new question instead")}
    quote={quote ? { text: quote.text, source: thread ? undefined : quote.source, id: thread ? undefined : 'branch-selection' } : null}
    onremovequote={() => (app.quote = null)}
    {options}
  />
</section>

<style>
  .check {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .back {
    color: var(--accent);
  }

  .target-title {
    font-weight: 600;
    color: var(--ink-soft);
  }

  .target-title :global(p) {
    display: inline;
  }
</style>
