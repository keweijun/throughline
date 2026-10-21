<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import QuestionThread from './QuestionThread.svelte';

  let question = $state('');
  let pause = $state(false);
  let busy = $state(false);

  const questions = $derived([...(app.state?.questions ?? [])].reverse());
  const currentLesson = $derived(app.lessons(app.currentId).at(-1));

  async function ask(event: SubmitEvent) {
    event.preventDefault();
    if (!question.trim()) return;
    busy = true;
    const quote = app.quote;
    const result = await app.act(() =>
      api.post('/api/questions', {
        id: newId(),
        question,
        selection: quote ? (quote.source ? `${quote.text}\n(${quote.source})` : quote.text) : '',
        selected_turn_id: quote?.turnId ?? null,
        main_turn_id: currentLesson?.id ?? null,
        anchor: { scroll_y: quote?.scrollY ?? window.scrollY, concept_id: app.viewingId },
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
    {#if app.quote}
      <div class="quote">
        <blockquote id="branch-selection">{app.quote.text}</blockquote>
        {#if app.quote.source}<p class="from">{t("From {source}", { source: app.quote.source })}</p>{/if}
        <button type="button" class="btn btn-quiet btn-small" onclick={() => (app.quote = null)}>{t("Remove quote")}</button>
      </div>
    {/if}
    <label class="field">
      <span class="visually-hidden">{t("Side question")}</span>
      <textarea
        id="question-input"
        rows="3"
        bind:value={question}
        aria-label={t("Side question")}
        placeholder={app.quote ? t("What would you like explained about this passage?") : t("What would you like explained?")}
        onkeydown={(e) => e.key === 'Enter' && (e.metaKey || e.ctrlKey) && (e.currentTarget.form as HTMLFormElement).requestSubmit()}
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
    <h3 class="list-title">{t("Your questions")}</h3>
    <div class="list">
      {#each questions as q (q.id)}
        <QuestionThread question={q} />
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
    margin: 2rem 0 0.75rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .list {
    display: grid;
    gap: 1rem;
  }
</style>
