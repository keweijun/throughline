<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Composer from './Composer.svelte';

  let { conceptId, hasLesson }: { conceptId: string; hasLesson: boolean } = $props();

  // The request is a draft per section, so it survives looking at another section.
  const draftKey = $derived(`lesson:${conceptId}`);
  const prompt = $derived(app.drafts.get(draftKey));
  const setPrompt = (value: string) => app.drafts.set(draftKey, value);
  let busy = $state(false);
  const running = $derived(app.runningLesson);
  // Before the first lesson the request is optional, so the card leads with starting and opens the box only on request
  // (or when a draft is waiting in it).
  let focusing = $state(false);
  const writing = $derived(hasLesson || focusing || prompt.trim() !== '');

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
    const result = await app.startLesson(sent);
    busy = false;
    if (result && app.drafts.get(key) === sent) app.drafts.set(key, '');
  }
</script>

{#if !running || running.concept_id !== conceptId}
  <div class="request" class:first={!hasLesson}>
    {#if !hasLesson}
      <h2>{t("Start this section")}</h2>
      {@const chapter = app.chapterOf(conceptId)}
      <p>
        {#if !chapter || chapter.concept_ids[0] === conceptId}{t("The teacher opens with an overview of the whole chapter, then teaches this section in short steps. You can pause at any time.")}
        {:else}{t("The teacher connects this section to the previous one, then teaches it in short steps. You can pause at any time.")}{/if}
      </p>
    {/if}
    {#snippet target()}{hasLesson ? t("Ask for another pass") : t("What the lesson focuses on · optional")}{/snippet}
    {#if !writing}
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
      placeholder={hasLesson ? t("For example: go deeper on the derivation, or explain it with a different example") : t("Leave empty for a full lesson: intuition, formulas and derivations, then an example.")}
      submitLabel={hasLesson ? t("Teach again") : t("Start lesson")}
      disabled={busy || !!running}
      allowEmpty
      onsubmit={start}
      header={target}
      onclose={hasLesson ? undefined : dropFocus}
      closeLabel={t("Start without a focus")}
    />
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

  .hint {
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
