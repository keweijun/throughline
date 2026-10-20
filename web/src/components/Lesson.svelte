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
    (app.state?.questions ?? [])
      .filter((q) => q.selection && (q.selected_turn_id ?? q.main_turn_id) === turn.id)
      .map((q) => q.selection),
  );

  $effect(() => {
    if (!body) return;
    void turn.text;
    markAsked(turn.id, body, asked);
    return () => clearAsked(turn.id);
  });
</script>

<section class="lesson" id="turn-{turn.id}" data-turn-id={turn.id} aria-label={lessons.length > 1 ? t('Lesson {number}', { number }) : 'Lesson'}>
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
    <div
      class="prose lesson-body"
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
    scroll-margin-top: calc(var(--topbar) + 1rem);
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
