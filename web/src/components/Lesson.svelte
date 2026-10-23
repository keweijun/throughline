<script lang="ts">
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { mark, clear } from '../lib/highlight';
  import { lessonStatus } from '../lib/format';
  import type { Turn } from '../lib/types';
  import TurnControls from './TurnControls.svelte';

  let { turn }: { turn: Turn } = $props();

  let body: HTMLElement | undefined = $state();
  const status = $derived(lessonStatus[turn.status]);
  const lessons = $derived(app.lessons(turn.concept_id));
  const number = $derived(lessons.findIndex((t) => t.id === turn.id) + 1);
  const asked = $derived(
    (app.state?.questions ?? []).filter((q) => q.selection && (q.selected_turn_id ?? q.main_turn_id) === turn.id),
  );
  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.turn_id === turn.id && a.passage));

  // Margin markers sit level with the passage: one for questions asked about it, one for the learner's notes on it.
  type Row = { top: number; questions: string[]; notes: string[] };
  let rows = $state<Row[]>([]);
  let width = $state(0);
  let fonts = $state(false);
  document.fonts?.ready.then(() => (fonts = true));

  $effect(() => {
    if (!body) return;
    void turn.text;
    void width;
    void fonts;
    const origin = body.getBoundingClientRect().top;
    const found: Row[] = [];
    const place = (range: Range | null, add: (row: Row) => void) => {
      if (!range) return;
      const top = Math.round(range.getClientRects()[0]?.top - origin);
      let row = found.find((r) => Math.abs(r.top - top) < 24);
      if (!row) found.push((row = { top, questions: [], notes: [] }));
      add(row);
    };
    mark('asked', turn.id, body, asked.map((q) => q.selection)).forEach((range, i) => place(range, (row) => row.questions.push(asked[i].id)));
    mark('mine', turn.id, body, mine.map((a) => a.passage)).forEach((range, i) => {
      if (mine[i].note) place(range, (row) => row.notes.push(mine[i].id));
    });
    rows = found;
    return () => {
      clear('asked', turn.id);
      clear('mine', turn.id);
    };
  });

  function openThread(id: string) {
    app.focusThread = id;
    app.openPanel('questions');
  }
</script>

<section class="lesson" id="turn-{turn.id}" data-turn-id={turn.id} aria-label={lessons.length > 1 ? t('Lesson {number}', { number }) : t('Lesson')}>
  <div class="meta">
    {#if lessons.length > 1}<span class="number">{t('Lesson {number}', { number })}</span>{/if}
    {#if turn.status === 'running'}
      <span class="chip"><span class="live-dot"></span>{diagnostic(status.label)}</span>
    {:else if turn.status !== 'completed'}
      <span class="chip chip-{status.tone}">{diagnostic(status.label)}</span>
    {/if}
    <TurnControls {turn} pauseLabel={t("Pause")} regenerateLabel={t("Regenerate lesson")} />
  </div>

  {#if turn.error && turn.status !== 'completed'}
    <p class="error">{diagnostic(turn.error)}</p>
  {/if}

  {#if turn.text}
    <div class="notes" aria-label={t("Questions and notes on this lesson")}>
      {#each rows as row}
        <div class="markers" style:top="{row.top}px">
          {#if row.notes.length}
            <button
              class="note mine"
              onclick={() => app.showAnnotation(row.notes[0])}
              aria-label={t("Open your note on this passage")}
              title={t("Your note on this passage")}
            >
              <span aria-hidden="true">✎</span>{#if row.notes.length > 1}<sup>{row.notes.length}</sup>{/if}
            </button>
          {/if}
          {#if row.questions.length}
            <button
              class="note"
              onclick={() => openThread(row.questions[0])}
              aria-label={t("Open your question about this passage")}
              title={row.questions.length > 1 ? t('{count} questions about this passage', { count: row.questions.length }) : t('Your question about this passage')}
            >
              <span aria-hidden="true">?</span>{#if row.questions.length > 1}<sup>{row.questions.length}</sup>{/if}
            </button>
          {/if}
        </div>
      {/each}
    </div>
    <div
      class="prose lesson-body"
      bind:clientWidth={width}
      bind:this={body}
      use:markdown={{ language: locale.language, text: turn.text, refs: turn.source_refs, onSource: (ref) => app.openSource(ref) }}
    ></div>
  {:else if turn.status === 'running'}
    <p class="waiting">{t("The teacher is reading the goal and sources. Text appears here as it is written.")}</p>
  {/if}

  {#if turn.attempts.length}
    <details class="attempts">
      <summary>{t('Earlier unfinished attempts')}</summary>
      {#each turn.attempts as attempt}
        <div class="prose attempt" use:markdown={{ language: locale.language, text: attempt.text || t("(No text was received.)") }}></div>
      {/each}
    </details>
  {/if}
</section>

<style>
  .lesson {
    position: relative;
    scroll-margin-top: calc(var(--topbar) + 1rem);
  }

  .notes {
    position: relative;
    height: 0;
  }

  .markers {
    position: absolute;
    right: calc(100% + 1rem);
    display: flex;
    gap: 0.3rem;
    margin-top: 0.15rem;
  }

  .note {
    position: relative;
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    padding: 0;
    border: 1px solid #c9a82b;
    border-radius: 50% 50% 50% 4px;
    background: var(--marker);
    color: #2a2208;
    font-family: var(--sans);
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.15s;
  }

  .note.mine {
    border-color: var(--mine);
    background: var(--mine-wash);
    color: var(--ink);
  }

  .note:hover,
  .note:focus-visible {
    transform: scale(1.12) rotate(-6deg);
  }

  .note sup {
    position: absolute;
    top: -0.45rem;
    right: -0.45rem;
    min-width: 1rem;
    border-radius: 999px;
    background: var(--accent);
    color: var(--on-accent);
    font-size: 0.62rem;
    line-height: 1rem;
  }

  @media (max-width: 56rem) {
    .markers {
      right: -0.6rem;
      flex-direction: column;
    }

    .note {
      width: 1.3rem;
      height: 1.3rem;
      font-size: 0.7rem;
    }
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
    min-height: 0;
    margin-bottom: 0.75rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .meta:not(:has(> *:not(:empty))) {
    display: none;
  }

  .number {
    font-weight: 600;
  }

  .error {
    margin-bottom: 1rem;
    padding: 0.6rem 0.8rem;
    border-radius: var(--radius);
    background: var(--danger-wash);
    color: var(--danger);
    font-size: var(--step-0);
  }

  .waiting {
    font-family: var(--serif);
    font-style: italic;
    color: var(--pencil);
    font-size: var(--reading);
  }

  .attempts {
    margin-top: 1.5rem;
    font-size: var(--step-0);
    color: var(--pencil);
  }

  .attempts summary {
    cursor: pointer;
  }

  .attempt {
    margin-top: 0.75rem;
    padding-left: 1rem;
    border-left: 2px solid var(--rule);
    font-size: var(--step-0);
    color: var(--ink-soft);
  }
</style>
