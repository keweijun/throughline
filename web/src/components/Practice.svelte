<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import Exercise from './Exercise.svelte';

  let { conceptId, isCurrent }: { conceptId: string; isCurrent: boolean } = $props();

  let busy = $state(false);

  const practice = $derived(app.state?.practice ?? { tasks: [], jobs: [] });
  const all = $derived(practice.tasks.filter((t) => t.concept_id === conceptId));
  const tasks = $derived(all.filter((t) => t.origin !== 'recap'));
  // Retrieval questions that close a chapter recap (ADR 0008), kept apart from the section's own exercises.
  const recap = $derived(all.filter((t) => t.origin === 'recap'));
  const recapGenerating = $derived(practice.jobs.some((j) => j.concept_id === conceptId && j.purpose === 'recap' && app.isRunning(j.id)));
  const recapFailed = $derived.by(() => {
    const last = practice.jobs.filter((j) => j.concept_id === conceptId && j.purpose === 'recap').at(-1);
    return !recap.length && last?.error ? last : undefined;
  });
  const earlier = $derived(isCurrent ? practice.tasks.filter((t) => t.concept_id !== conceptId && !solved(t)) : []);
  const generating = $derived(practice.jobs.some((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose && app.isRunning(j.id)));

  const failed = $derived(practice.jobs.filter((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose && j.error).at(-1));
  const interrupted = $derived(
    practice.jobs.some((j) => {
      if (j.concept_id !== conceptId || j.action !== 'generate' || j.purpose || j.processed) return false;
      const turn = app.turn(j.id);
      return turn && turn.status !== 'running' && turn.status !== 'completed';
    }),
  );
  const hasLesson = $derived(app.hasLesson(conceptId));

  async function generate() {
    busy = true;
    await app.act(() => api.post('/api/practice/generate', { concept_id: conceptId }));
    busy = false;
  }
</script>

{#if all.length || earlier.length || generating || recapGenerating || (isCurrent && hasLesson)}
  <section class="practice" id="practice" aria-labelledby="practice-title">
    <header>
      <h2 id="practice-title">{t("Practice")}</h2>
      <p>{t("Answers you give on your own, with hints, or after seeing a solution are recorded separately. Practice is optional before moving on.")}</p>
    </header>

    {#if generating}
      <p class="status"><span class="chip"><span class="live-dot"></span>{t("Preparing exercises")}</span></p>
    {:else if !tasks.length && isCurrent}
      {#if failed}
        <p class="problem">{t("The exercises could not be prepared:")} {diagnostic(failed.error ?? "")}</p>
      {:else if interrupted}
        <p class="problem">{t("Preparing exercises stopped before it finished.")}</p>
      {/if}
      <button class="btn" disabled={busy} onclick={generate}>{failed || interrupted ? t("Try again") : t("Prepare exercises")}</button>
    {/if}

    {#each tasks as task, i (task.id)}
      <Exercise {task} number={i + 1} />
    {/each}

    {#if recap.length || recapGenerating || recapFailed}
      <section class="recap" aria-labelledby="recap-questions-title">
        <h3 id="recap-questions-title">{t("Chapter recap questions")}</h3>
        <p class="note">{t("Answer from memory. Each one also counts as a review of the sections it tests.")}</p>
        {#if recapGenerating}
          <p class="status"><span class="chip"><span class="live-dot"></span>{t("Preparing recap questions")}</span></p>
        {:else if recapFailed}
          <p class="problem">{t("The recap questions could not be prepared:")} {diagnostic(recapFailed.error ?? "")}</p>
        {/if}
        {#each recap as task, i (task.id)}
          <Exercise {task} number={i + 1} />
        {/each}
      </section>
    {/if}

    {#if earlier.length}
      <details class="earlier">
      <summary>{t("Still open from earlier sections")} <span>({earlier.length})</span></summary>
      <div class="earlier-tasks">
      {#each earlier as task (task.id)}
        <Exercise {task} showSection />
      {/each}
      </div>
      </details>
    {/if}
  </section>
{/if}

<style>
  .practice {
    display: grid;
    gap: 1.25rem;
    margin-top: 3.5rem;
    padding-top: 2rem;
    border-top: 1px solid var(--rule-strong);
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-3);
    font-weight: 600;
  }

  header p {
    margin-top: 0.35rem;
    color: var(--pencil);
    font-size: var(--step-0);
  }

  .earlier-tasks { display: grid; gap: 1rem; margin-top: 1rem; }

  .recap {
    display: grid;
    gap: 1rem;
    margin-top: 1rem;
  }

  h3 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  .recap .note {
    margin-top: -0.6rem;
    color: var(--pencil);
    font-size: var(--step-0);
  }

  summary {
    cursor: pointer;
    margin-top: 1rem;
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .problem {
    color: var(--danger);
    font-size: var(--step-0);
  }

  .practice > .btn {
    justify-self: start;
  }
</style>
