<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';

  const prep = $derived(app.state?.preparation);
  const job = $derived(prep?.jobs.filter((j) => j.concept_id === prep?.next_concept_id).at(-1));
  const next = $derived(app.concept(prep?.next_concept_id));

  const text = $derived.by(() => {
    switch (job?.status) {
      case 'running':
        return t("Preparing in the background while you read.");
      case 'ready':
        return t("Prepared by the teacher in the background.");
      case 'deferred':
        return t("Preparation paused so your own requests go first.");
      case 'failed':
        return t("Preparation failed. The teacher will prepare when you start that section.");
      case 'stale':
        return t("The route or sources changed, so the teacher will prepare when you start that section.");
      default:
        return t("Will be prepared in the background when nothing else is running.");
    }
  });
</script>

{#if next}
  <p class="prep" role="status" id="preparation-status">
    <span>{text}</span>
    {#if job?.status === 'failed'}
      <button class="btn btn-quiet btn-small" onclick={() => app.act(() => api.post('/api/preparation/retry'))}>{t("Retry preparation")}</button>
    {/if}
  </p>
{/if}

<style>
  .prep {
    animation: enter-fade var(--settle) ease;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.75rem;
    margin-top: 0.35rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
