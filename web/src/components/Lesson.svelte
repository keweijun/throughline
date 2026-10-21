<script lang="ts">
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { markAsked, clearAsked } from '../lib/highlight';
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

  // Margin notes sit level with the passage each question was asked about.
  let notes = $state<{ top: number; ids: string[] }[]>([]);
  let width = $state(0);
  let fonts = $state(false);
  document.fonts?.ready.then(() => (fonts = true));

  $effect(() => {
    if (!body) return;
    void turn.text;
    void width;
    void fonts;
    const found = markAsked(turn.id, body, asked.map((q) => q.selection));
    const origin = body.getBoundingClientRect().top;
    const rows: { top: number; ids: string[] }[] = [];
    found.forEach((range, i) => {
      if (!range) return;
      const top = Math.round(range.getClientRects()[0]?.top - origin);
      const row = rows.find((r) => Math.abs(r.top - top) < 24);
      if (row) row.ids.push(asked[i].id);
      else rows.push({ top, ids: [asked[i].id] });
    });
    notes = rows;
    return () => clearAsked(turn.id);
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
    <div class="notes" aria-label={t("Questions asked about this lesson")}>
      {#each notes as note}
        <button
          class="note"
          style:top="{note.top}px"
          onclick={() => openThread(note.ids[0])}
          aria-label={t("Open your question about this passage")}
          title={note.ids.length > 1 ? t('{count} questions about this passage', { count: note.ids.length }) : t('Your question about this passage')}
        >
          <span aria-hidden="true">?</span>{#if note.ids.length > 1}<sup>{note.ids.length}</sup>{/if}
        </button>
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

  .note {
    position: absolute;
    left: -2.6rem;
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    margin-top: 0.15rem;
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
    .note {
      left: auto;
      right: -0.6rem;
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
