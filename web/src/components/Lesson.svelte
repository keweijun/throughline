<script lang="ts">
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown, RENDERED } from '../lib/markdown';
  import { mark, clear } from '../lib/highlight';
  import { lessonStatus } from '../lib/format';
  import type { Turn } from '../lib/types';
  import TurnControls from './TurnControls.svelte';

  let { turn }: { turn: Turn } = $props();

  let body: HTMLElement | undefined = $state();
  const status = $derived(lessonStatus[turn.status]);
  const lessons = $derived(app.lessons(turn.concept_id));
  // A stepped lesson (ADR 0009) counts once among the section's lessons, however many steps it has.
  const step = $derived(app.stepOf(turn.id));
  const units = $derived([...new Set(lessons.map((l) => app.stepOf(l.id)?.lesson.id ?? l.id))]);
  const number = $derived(units.indexOf(step?.lesson.id ?? turn.id) + 1);
  const planned = $derived(step ? step.lesson.steps.slice(step.number) : []);
  // Continue is offered under the latest step once it is complete and the plan has steps left.
  const continues = $derived(
    !!step && turn.status === 'completed' && planned.length > 0 && !planned.some((s) => s.turn_id),
  );
  let continuing = $state(false);

  async function next() {
    if (!step || continuing) return;
    continuing = true;
    await app.continueLesson(step.lesson.id);
    continuing = false;
  }
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
  // While streaming, the body is patched a frame after the text changes; re-place markers once it is.
  let renders = $state(0);
  $effect(() => {
    if (!body) return;
    const count = () => renders++;
    body.addEventListener(RENDERED, count);
    return () => body?.removeEventListener(RENDERED, count);
  });

  $effect(() => {
    if (!body) return;
    void renders;
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

<section
  class="lesson"
  class:step={!!step}
  id="turn-{turn.id}"
  data-turn-id={turn.id}
  aria-label={turn.id.startsWith('recap:') ? t("Chapter recap")
    : step ? t('Step {number} of {total}', { number: step.number, total: step.lesson.steps.length })
    : units.length > 1 ? t('Lesson {number}', { number }) : t('Lesson')}
>
  <div class="meta">
    {#if turn.id.startsWith('recap:')}<span class="number">{t("Chapter recap")}</span>
    {:else if units.length > 1}<span class="number">{t('Lesson {number}', { number })}</span>{/if}
    {#if step}
      <span class="number step-position">{t('Step {number} of {total}', { number: step.number, total: step.lesson.steps.length })}</span>
      <span class="step-title">{step.lesson.steps[step.number - 1].title}</span>
      {#if step.lesson.steps[step.number - 1].added}<span class="chip chip-accent">{t("Added step")}</span>{/if}
    {/if}
    {#if turn.status === 'running'}
      <span class="chip"><span class="live-dot"></span>{t(status.label)}</span>
    {:else if turn.status !== 'completed'}
      <span class="chip chip-{status.tone}">{t(status.label)}</span>
    {/if}
    <TurnControls {turn} pauseLabel={t("Pause")} regenerateLabel={step ? t("Regenerate step") : t("Regenerate lesson")} />
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
      use:markdown={{ language: locale.language, text: turn.text, refs: turn.source_refs, onSource: (ref) => app.openSource(ref), streaming: turn.status === 'running' }}

    ></div>
  {:else if turn.status === 'running'}
    <p class="waiting">{t("The teacher is reading the goal and sources. Text appears here as it is written.")}</p>
  {/if}

  {#if continues}
    <div class="next" role="group" aria-label={t("Next step")}>
      <ol class="plan" start={step!.number + 1}>
        {#each planned as item}
          <li>{item.title}{#if item.added} <span class="chip chip-accent">{t("Added step")}</span>{/if}</li>
        {/each}
      </ol>
      <div class="row">
        <button class="btn btn-primary" onclick={next} disabled={continuing || !!app.runningLesson}>{t("Continue")}</button>
        {#if app.runningLesson}<span class="hint">{t("Another lesson is being written. Pause it first.")}</span>{/if}
      </div>
    </div>
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
    animation: enter-rise var(--settle) var(--ease-out);
    position: relative;
    scroll-margin-top: 1rem;
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

  .step-title {
    color: var(--ink-soft);
  }

  .next {
    display: grid;
    gap: 0.75rem;
    margin-top: 1.75rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
    font-size: var(--step-0);
  }

  .plan {
    margin: 0;
    padding-left: 1.4rem;
    color: var(--ink-soft);
  }

  .plan li:first-child {
    color: var(--ink);
    font-weight: 600;
  }

  .next .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .next .hint {
    font-size: var(--step--1);
    color: var(--pencil);
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
