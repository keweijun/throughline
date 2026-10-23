<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { api, newId } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';

  let { conceptId }: { conceptId: string } = $props();

  let busy = $state(false);

  const route = $derived(app.state?.curriculum.route ?? []);
  const next = $derived(app.concept(route[route.indexOf(conceptId) + 1]));
  const pending = $derived(
    app.tasks(conceptId).filter((task) => !solved(task)).length,
  );
  const activeSupplement = $derived((app.state?.questions ?? []).some((q) => q.choice === 'accept' && !q.returned));

  async function advance() {
    busy = true;
    await app.act(() => api.post('/api/sections/next', { concept_id: conceptId, request_id: newId() }));
    busy = false;
    window.scrollTo({ top: 0 });
  }
</script>

{#if next}
  <section class="next" aria-label={t("Next section")}>
    <div>
      <p class="label">{t("Up next")}</p>
      <p class="title">{next.title}</p>
      {#if activeSupplement}
        <p class="note">{t("Finish or close the foundation supplement in Questions before moving on.")}</p>
      {:else if pending}
        <p class="note">{t('{count} exercises stay open and will be waiting for you.', { count: pending })}</p>
      {/if}
    </div>
    <button class="btn btn-primary" disabled={busy || activeSupplement} onclick={advance}>{t("Enter next section")}</button>
  </section>
{:else if !next && app.hasLesson(conceptId)}
  <section class="next done" aria-label={t("End of route")}>
    <p class="title">{t("This is the last section on the route.")}</p>
  </section>
{/if}

<style>
  .next {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 3rem;
    padding: 1.25rem 1.35rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
  }

  .label {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .title {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
  }

  .note {
    margin-top: 0.2rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .done {
    background: transparent;
    border: 1px dashed var(--rule-strong);
  }
</style>
