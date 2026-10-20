<script lang="ts">
  import { app } from '../lib/store.svelte';

  let { conceptId, hasLesson }: { conceptId: string; hasLesson: boolean } = $props();

  let prompt = $state('');
  let busy = $state(false);
  const running = $derived(app.runningLesson);

  async function start(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    const result = await app.startLesson(prompt);
    busy = false;
    if (result) prompt = '';
  }
</script>

{#if !running || running.concept_id !== conceptId}
  <form class="composer" class:first={!hasLesson} onsubmit={start}>
    {#if hasLesson}
      <label class="field">
        <span>Ask for another pass</span>
        <textarea
          id="lesson-prompt"
          rows="2"
          bind:value={prompt}
          placeholder="For example: go deeper on the derivation, or explain it with a different example"
        ></textarea>
      </label>
      <div class="row">
        <button class="btn" type="submit" disabled={busy || !!running}>Teach again</button>
        {#if running}<span class="hint">Another lesson is being written. Pause it first.</span>{/if}
      </div>
    {:else}
      <h2>Start this section</h2>
      <p>The teacher opens with a unit overview, then teaches the section in one pass. You can pause at any time.</p>
      <details>
        <summary>Change what the lesson focuses on</summary>
        <label class="field">
          <span class="visually-hidden">Lesson request</span>
          <textarea id="lesson-prompt" rows="3" bind:value={prompt} placeholder="Leave empty for a full lesson: intuition, formulas and derivations, then an example."></textarea>
        </label>
      </details>
      <div class="row">
        <button class="btn btn-primary" id="start" type="submit" disabled={busy || !!running}>Start lesson</button>
        {#if running}<span class="hint">Another lesson is being written. Pause it first.</span>{/if}
      </div>
    {/if}
  </form>
{/if}

<style>
  .composer {
    display: grid;
    gap: 0.75rem;
    margin-top: 2.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--rule);
  }

  .composer.first {
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

  summary {
    cursor: pointer;
    color: var(--accent);
    font-size: var(--step-0);
    font-weight: 500;
  }

  details[open] summary {
    margin-bottom: 0.6rem;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .hint {
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
