<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { LessonKind } from '../lib/types';
  import Composer from './Composer.svelte';

  // `open`: the section's lesson has steps left, so Continue is the way on and this only offers to start it over.
  let { conceptId, hasLesson, open = false }: { conceptId: string; hasLesson: boolean; open?: boolean } = $props();

  // The request is a draft per section, so it survives looking at another section.
  const draftKey = $derived(`lesson:${conceptId}`);
  const prompt = $derived(app.drafts.get(draftKey));
  const setPrompt = (value: string) => app.drafts.set(draftKey, value);
  let busy = $state(false);
  const running = $derived(app.runningLesson);
  // The box opens only when asked for (or when a draft is waiting in it): before the first lesson the card leads with
  // starting; under a finished lesson, teaching it again is one quiet offer; mid-lesson, so is starting over.
  let focusing = $state(false);
  const writing = $derived(focusing || prompt.trim() !== '');
  // Over a taught section: another pass adds one reply to the lesson there; a New lesson replaces it (ADR 0023).
  let chosen = $state<LessonKind>('pass');
  $effect(() => {
    void conceptId;
    chosen = 'pass'; // each section starts from another pass
  });
  const kind = $derived<LessonKind | undefined>(open ? 'new' : hasLesson ? chosen : undefined);

  function chooseFocus() {
    focusing = true;
    requestAnimationFrame(() => document.getElementById('lesson-prompt')?.focus());
  }

  function dropFocus() {
    setPrompt('');
    focusing = false;
  }

  async function start() {
    if (busy || running) return;
    busy = true;
    const sent = prompt;
    const key = draftKey;
    const result = await app.startLesson(sent, kind);
    busy = false;
    if (result && app.drafts.get(key) === sent) app.drafts.set(key, '');
    if (result) {
      focusing = false;
      chosen = 'pass';
    }
  }
</script>

{#if !running || running.concept_id !== conceptId}
  <div class="request" class:first={!hasLesson} class:quiet={hasLesson && !writing}>
    {#if !hasLesson}
      <h2>{t("Start this section")}</h2>
      {@const chapter = app.chapterOf(conceptId)}
      <p>
        {#if !chapter || chapter.concept_ids[0] === conceptId}{t("The teacher opens with an overview of the whole chapter, then teaches this section in short steps. You can pause at any time.")}
        {:else}{t("The teacher connects this section to the previous one, then teaches it in short steps. You can pause at any time.")}{/if}
      </p>
    {/if}
    {#snippet target()}
      {#if open}{t("New lesson · replaces this one")}
      {:else if hasLesson}
        <div class="segmented" role="radiogroup" aria-label={t("What to ask for")}>
          <label><input type="radio" name="lesson-kind-{conceptId}" value="pass" bind:group={chosen} />{t("Another pass")}</label>
          <label><input type="radio" name="lesson-kind-{conceptId}" value="new" bind:group={chosen} />{t("New lesson")}</label>
        </div>
      {:else}{t("What the lesson focuses on · optional")}{/if}
    {/snippet}
    {#if open && !writing}
      <!-- Under a lesson still going on, the other choice sits right, below its Continue. -->
      <div class="row instead">
        <button class="btn btn-quiet btn-small" disabled={busy || !!running} onclick={chooseFocus}>{t("Start a new lesson instead")}</button>
      </div>
    {:else if hasLesson && !writing}
      <div class="row instead">
        <button class="btn btn-quiet btn-small" disabled={busy || !!running} onclick={chooseFocus}>{t("Teach again…")}</button>
      </div>
    {:else if !writing}
      <div class="row">
        <button class="btn btn-primary" disabled={busy || !!running} onclick={start}>{t("Start lesson")}</button>
        <button class="btn btn-quiet" onclick={chooseFocus}>{t("Choose a focus")}</button>
      </div>
    {:else}
    <Composer
      id="lesson-prompt"
      value={prompt}
      onvalue={setPrompt}
      label={t("Lesson request")}
      placeholder={kind === 'new' ? t("Leave empty to teach the whole section again in steps, or say what it should cover: only what the last lesson skipped, more rigour, the proofs")
        : kind === 'pass' ? t("For example: go deeper on the derivation, or explain it with a different example")
        : t("Leave empty for a full lesson: intuition, formulas and derivations, then an example.")}
      submitLabel={kind === 'new' ? t("Start new lesson") : kind === 'pass' ? t("Teach again") : t("Start lesson")}
      disabled={busy || !!running}
      allowEmpty
      onsubmit={start}
      header={target}
      onclose={dropFocus}
      closeLabel={open || hasLesson ? t("Keep this lesson") : t("Start without a focus")}
    />
    {#if kind === 'new'}
      <p class="hint">{open ? t("The steps you have read stay above, folded; the rest of this lesson's plan is dropped.") : t("The lesson you have read stays above, folded, with your answers and notes.")}</p>
    {/if}
    {/if}
    {#if running}<p class="hint">{t("Another lesson is being written. Pause it first.")}</p>{/if}
  </div>
{/if}

<style>
  .request {
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    gap: 0.75rem;
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
  }

  /* Folded to one quiet offer under a lesson, it needs no rule of its own: the lesson's end and Practice's frame it. */
  .request.quiet {
    margin-top: 0.75rem;
    padding-top: 0;
    border-top: 0;
  }

  .request.first {
    margin-top: 0;
    padding: 1.5rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  p {
    color: var(--ink-soft);
    font-size: var(--step-0);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .row.instead {
    justify-content: flex-end;
  }

  .hint {
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
