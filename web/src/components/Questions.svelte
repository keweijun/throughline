<script lang="ts">
  import { enterToSend } from '../lib/keys';
  import { slide } from 'svelte/transition';
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { stageScroll } from '../lib/stage';
  import { autogrow } from '../lib/autogrow';
  import { questionTurnIds } from '../lib/format';

  import QuestionThread from './QuestionThread.svelte';
  import type { Question } from '../lib/types';

  let question = $state('');
  let pause = $state(false);
  let busy = $state(false);

  const questions = $derived([...(app.state?.questions ?? [])].sort((a, b) => (b.created_at ?? app.turn(b.turn_id)?.started_at ?? 0) - (a.created_at ?? app.turn(a.turn_id)?.started_at ?? 0)));
  const currentLesson = $derived(app.lessons(app.currentId).at(-1));

  // Many questions: show this section's by default, searchable, with only the newest and active ones expanded.
  let scope = $state<'section' | 'all'>('section');
  let scopeChosen = false;
  let search = $state('');
  let opened = $state<Record<string, boolean>>({});
  const sectionOf = (q: Question) => q.anchor?.concept_id ?? q.restore_point?.concept_id;
  const inSection = $derived(questions.filter((q) => sectionOf(q) === app.viewingId));
  // Until the learner picks a scope, follow what is useful: this section if it has questions, otherwise all.
  $effect(() => {
    if (!scopeChosen) scope = inSection.length ? 'section' : 'all';
  });
  const turnsOf = (q: Question) => questionTurnIds(q).map((id) => app.turn(id));
  const active = (q: Question) => q.status === 'suggested' || questionTurnIds(q).some((id) => app.isRunning(id));
  // A few questions can all be read at once; with more, only one being answered opens by itself, and stays open after.
  const isOpen = (q: Question) => opened[q.id] ?? (questions.length <= 3 || active(q));
  $effect(() => {
    for (const q of questions) if (opened[q.id] === undefined && active(q)) opened[q.id] = true;
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

  async function ask(event: SubmitEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    busy = true;
    const quote = app.quote?.questionId ? null : app.quote;
    const result = await app.act(() =>
      api.post('/api/questions', {
        id: newId(),
        question,
        selection: quote ? (quote.source ? `${quote.text}\n(${quote.source})` : quote.text) : '',
        selected_turn_id: quote?.turnId ?? null,
        main_turn_id: currentLesson?.id ?? null,
        anchor: { scroll_y: quote?.scrollY ?? stageScroll(), concept_id: app.viewingId },
        pause,
      }),
    );
    busy = false;
    if (result) {
      question = '';
      pause = false;
      app.quote = null;
    }
  }
</script>

<section id="branch-panel">
  <form class="ask" onsubmit={ask}>
    <h2>{t("Ask a side question")}</h2>
    <p class="intro">{t("Select a sentence or formula in a lesson or the source reader to ask about it. The lesson keeps going unless you pause it.")}</p>
    {#if app.quote && !app.quote.questionId}
      <div class="quote">
        <blockquote id="branch-selection" class="prose" use:markdown={{ language: locale.language, text: app.quote.text }}></blockquote>
        {#if app.quote.source}<p class="from">{t("From {source}", { source: app.quote.source })}</p>{/if}
        <button type="button" class="btn btn-quiet btn-small" onclick={() => (app.quote = null)}>{t("Remove quote")}</button>
      </div>
    {/if}
    <label class="field">
      <span class="visually-hidden">{t("Side question")}</span>
      <textarea
        id="question-input"
        rows="3"
        bind:value={question} use:autogrow={question}
        aria-label={t("Side question")}
        placeholder={app.quote ? t("What would you like explained about this passage?") : t("What would you like explained?")}
        use:enterToSend
      ></textarea>
    </label>
    <div class="row">
      {#if app.runningLesson}
        <label class="check"><input type="checkbox" bind:checked={pause} /> {t("Pause the lesson while I ask")}</label>
      {/if}
      <button class="btn btn-primary" type="submit" disabled={busy || !question.trim()}>{t("Ask")}</button>
    </div>
  </form>

  {#if questions.length}
    <div class="list-head">
      <h3 class="list-title">{t("Your questions")}</h3>
      <div class="scope segmented" role="radiogroup" aria-label={t("Show questions from")} onchange={() => (scopeChosen = true)}>
        <label><input type="radio" bind:group={scope} value="section" />{t("This section ({count})", { count: inSection.length })}</label>
        <label><input type="radio" bind:group={scope} value="all" />{t("All ({count})", { count: questions.length })}</label>
      </div>
      {#if questions.length > 4}
        <input class="search" type="search" bind:value={search} aria-label={t("Search questions")} placeholder={t("Search questions and answers…")} />
      {/if}
    </div>
    <div class="list">
      {#each shown as q (q.id)}
        <div transition:slide={{ duration: 200 }}>
          <QuestionThread question={q} bind:open={() => isOpen(q), (value) => (opened[q.id] = value)} />
        </div>
      {:else}
        <p class="none">{search.trim() ? t("No questions match your search.") : t("No questions from this section yet.")}</p>
      {/each}
    </div>
  {/if}
</section>

<style>
  .ask {
    display: grid;
    gap: 0.7rem;
  }

  h2 {
    font-size: var(--step-1);
    font-weight: 600;
  }

  .intro {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .quote {
    display: grid;
    gap: 0.2rem;
  }

  blockquote {
    margin: 0;
    padding: 0.45rem 0.7rem;
    border-left: 3px solid var(--marker);
    background: var(--marker-wash);
    font-family: var(--serif);
    font-size: var(--step-0);
    max-height: 8rem;
    overflow: auto;
    white-space: pre-wrap;
  }

  .from {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .quote .btn {
    justify-self: start;
    padding-left: 0;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .row .btn {
    margin-left: auto;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .list-title {
    margin: 0;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .list-head {
    display: grid;
    gap: 0.5rem;
    margin: 2rem 0 0.9rem;
  }

  .scope {
    align-self: flex-start;
  }

  .search {
    font-size: var(--step--1);
  }

  .none {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .list {
    display: grid;
    gap: 1rem;
  }
</style>
