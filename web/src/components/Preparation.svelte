<script lang="ts">
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';

  const prep = $derived(app.state?.preparation);
  const job = $derived(prep?.jobs.filter((j) => j.concept_id === prep?.next_concept_id).at(-1));
  const next = $derived(app.concept(prep?.next_concept_id));

  const text = $derived.by(() => {
    switch (job?.status) {
      case 'running':
        return 'Preparing in the background while you read.';
      case 'ready':
        return 'Prepared. This is teacher material only; it does not count as learning.';
      case 'deferred':
        return 'Preparation paused so your own requests go first.';
      case 'failed':
        return 'Preparation failed. The teacher will prepare when you start that section.';
      case 'stale':
        return 'The route or sources changed, so the teacher will prepare when you start that section.';
      default:
        return 'Will be prepared in the background when nothing else is running.';
    }
  });
</script>

{#if next}
  <p class="prep" role="status" id="preparation-status">
    <span><strong>{next.title}:</strong> {text}</span>
    {#if job?.status === 'failed'}
      <button class="btn btn-quiet btn-small" onclick={() => app.act(() => api.post('/api/preparation/retry'))}>Retry preparation</button>
    {/if}
  </p>
{/if}

<style>
  .prep {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
    margin-top: 0.75rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  strong {
    font-weight: 600;
    color: var(--ink-soft);
  }
</style>
