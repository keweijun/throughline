<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { panelCoversLesson } from '../lib/media';
  import { stageScroll } from '../lib/stage';
  import { questionTurnIds } from '../lib/format';
  import { groupBySection, scopeCounts, type PanelScope as Scope } from '../lib/panel';

  import Composer from './Composer.svelte';
  import PanelGroups from './PanelGroups.svelte';
  import PanelScope from './PanelScope.svelte';
  import QuestionThread from './QuestionThread.svelte';
  import type { Question } from '../lib/types';

  let pause = $state(false);
  let busy = $state(false);

  // Oldest first, like a conversation: a new question appears just above the box it was typed in.
  const questions = $derived([...(app.state?.questions ?? [])].sort((a, b) => (a.created_at ?? app.turn(a.turn_id)?.started_at ?? 0) - (b.created_at ?? app.turn(b.turn_id)?.started_at ?? 0)));
  const currentLesson = $derived(app.lessons(app.currentId).at(-1));

  // Questions and Notes narrow and search their lists the same way.
  let scope = $state<Scope>('section');
  let scopeChosen = false;
  let search = $state('');
  // One thread is open at a time, so the list stays a list and the open question stays pinned above its answers.
  let openId = $state<string | null>(null);
  const sectionOf = (q: Question) => q.anchor?.concept_id ?? q.restore_point?.concept_id;
  const counts = $derived(scopeCounts(questions, sectionOf));
  // Until the learner picks a scope, show the narrowest one that has something in it.
  $effect(() => {
    if (!scopeChosen) scope = counts.section ? 'section' : counts.chapter ? 'chapter' : 'all';
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
  const words = $derived(search.toLowerCase().split(/\s+/).filter(Boolean));
  const matches = (q: Question) => {
    const text = [q.question, q.selection, ...(q.replies ?? []).map((r) => r.question), ...turnsOf(q).map((x) => x?.text ?? '')].join(' ').toLowerCase();
    return words.every((w) => text.includes(w));
  };
  const groups = $derived(groupBySection(questions.filter(matches), scope, sectionOf));
  const shown = $derived(groups.flatMap((g) => g.items));

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
  const images = $derived(app.drafts.images(draftKey));
  // A follow-up waits until every earlier answer in its thread has finished.
  const canReply = $derived(!thread || (
    app.turn(thread.turn_id)?.status === 'completed'
    && [thread.supplement_turn_id, ...(thread.replies ?? []).map((r) => r.turn_id)].every((id) => !id || app.turn(id)?.status === 'completed')
  ));

  async function send() {
    if (busy) return;
    busy = true;
    const text = draft;
    const attached = images;
    const key = draftKey;
    const target = thread;
    const id = newId();
    const withImages = attached.length ? { images: attached } : {};
    const result = await app.act(() => target
      ? api.post(`/api/questions/${encodeURIComponent(target.id)}/replies`, { id, question: text, selection: quote?.text ?? '', ...withImages })
      : api.post('/api/questions', {
          id,
          question: text,
          ...withImages,
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
    if (JSON.stringify(app.drafts.images(key)) === JSON.stringify(attached)) app.drafts.setImages(key, []);
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
    <div class="panel-bar"><h2 id="questions-title">{t("Your questions")}</h2></div>
    <p class="panel-intro">{t("Select a sentence or formula in a lesson or the source reader to ask about it. The lesson keeps going unless you pause it.")}</p>
    {#if questions.length}
      <PanelScope bind:scope {counts} label={t("Show questions from")} onchoose={() => (scopeChosen = true)} />
    {/if}
    {#if questions.length > 4}
      <div class="panel-tools">
        <input type="search" bind:value={search} aria-label={t("Search questions")} placeholder={t("Search questions and answers…")} />
      </div>
    {/if}
  </header>

  <div class="panel-list">
    {#snippet thread_(q: Question)}
      <QuestionThread question={q} bind:open={() => openId === q.id, (value) => setOpen(q, value)} />
    {/snippet}
    <PanelGroups
      {groups}
      {scope}
      key={(q) => q.id}
      item={thread_}
      empty={words.length ? t("No questions match your search.") : !questions.length ? t("No questions yet.") : scope === 'chapter' ? t("No questions in this chapter yet.") : t("No questions in this section yet.")}
    />
  </div>

  {#snippet target()}
    {#if thread}
      <span aria-hidden="true">↳</span> {t("Follow-up")} · <span class="target-title" use:markdown={{ language: locale.language, text: thread.question }}></span>
    {:else}
      {t("New question")}{#if app.viewingId} · {app.concept(app.viewingId)?.title}{/if}
    {/if}
  {/snippet}
  {#snippet tools()}
    {#if !thread && app.runningLesson}
      <button type="button" class="toggle" aria-pressed={pause} onclick={() => (pause = !pause)} title={t("Pause the lesson while I ask")}>
        <span class="mark" aria-hidden="true">{pause ? '❚❚' : '▶'}</span>{pause ? t("Lesson pauses") : t("Lesson keeps going")}
      </button>
    {/if}
  {/snippet}
  <div class="panel-foot">
    {#if thread && canReturn}
      <button type="button" class="btn btn-quiet btn-small btn-flush back" disabled={busy} onclick={backToLesson}>
        ← {thread.selection && thread.selected_turn_id ? t("Back to the passage") : t("Return to the lesson")}
      </button>
    {/if}
    <Composer
      id="question-input"
      value={draft}
      onvalue={(value) => app.drafts.set(draftKey, value)}
      label={thread ? t("Follow-up question") : t("Side question")}
      placeholder={thread ? t("Ask a follow-up about this…") : quote ? t("What would you like explained about this passage?") : t("What would you like explained?")}
      submitLabel={thread ? t("Send follow-up") : t("Ask")}
      disabled={busy || !canReply}
      onsubmit={send}
      header={target}
      onclose={thread ? () => setOpen(thread, false) : undefined}
      closeLabel={t("Ask a new question instead")}
      quote={quote ? { text: quote.text, source: thread ? undefined : quote.source, id: thread ? undefined : 'branch-selection' } : null}
      onremovequote={() => (app.quote = null)}
      imagesKey={draftKey}
      {tools}
    />
  </div>
</section>

<style>
  /* Whether the lesson keeps being written while the teacher answers: a switch on how the question is sent. */
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 1.9rem;
    padding: 0.15rem 0.6rem;
    border: 1px solid var(--rule);
    border-radius: 999px;
    background: none;
    color: var(--pencil);
    font-size: var(--step--1);
    cursor: pointer;
  }

  .toggle:hover {
    border-color: var(--pencil);
  }

  .toggle[aria-pressed='true'] {
    border-color: var(--caution);
    background: var(--caution-wash);
    color: var(--caution);
    font-weight: 600;
  }

  .mark {
    font-size: 0.6rem;
    letter-spacing: -0.05em;
  }

  .back {
    justify-self: start;
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
