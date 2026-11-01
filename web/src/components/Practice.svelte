<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { open, solved } from '../lib/format';
  import Exercise from './Exercise.svelte';
  import Composer from './Composer.svelte';

  let { conceptId, isCurrent }: { conceptId: string; isCurrent: boolean } = $props();

  let busy = $state(false);

  const practice = $derived(app.state?.practice ?? { tasks: [], jobs: [] });
  // The chapter quiz anchored to a last section is listed on the chapter page, not here.
  const tasks = $derived(app.tasks(conceptId));
  // One line says where the section's practice stands, so the cards need not be read to find out.
  const tally = $derived.by(() => {
    const counted = tasks.filter((t) => t.status !== 'skipped');
    const again = counted.filter((t) => !solved(t) && t.history.some((h) => h.action === 'assess')).length;
    return { solved: counted.filter(solved).length, total: counted.length, again };
  });
  const standing = $derived(
    [
      t("{solved} of {total} solved", tally),
      ...(tally.again ? [tally.again === 1 ? t("1 needs another try") : t("{count} need another try", { count: tally.again })] : []),
    ].join(' · '),
  );
  // Open exercises from the chapter's other sections; an earlier chapter keeps its own on its chapter page.
  const chapter = $derived(app.chapterOf(conceptId)?.id);
  const earlier = $derived(
    isCurrent ? practice.tasks.filter((t) => t.concept_id !== conceptId && !t.chapter_id && app.chapterOf(t.concept_id)?.id === chapter && open(t)) : [],
  );
  const generating = $derived(practice.jobs.some((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose && app.isRunning(j.id)));
  const writingVariant = $derived(practice.jobs.some((j) => j.concept_id === conceptId && j.action === 'generate' && j.variant_of && app.isRunning(j.id)));

  const failed = $derived(practice.jobs.filter((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose && j.error).at(-1));
  // A request for different exercises, or another like one, that ended without them; the exercises shown are unchanged.
  const latestRequest = $derived(
    practice.jobs
      .filter((j) => j.concept_id === conceptId && j.action === 'generate' && !j.purpose)
      .sort((a, b) => (app.turn(a.id)?.started_at ?? 0) - (app.turn(b.id)?.started_at ?? 0))
      .at(-1),
  );
  const requestFailed = $derived(tasks.length && latestRequest?.error && (latestRequest.replaces || latestRequest.variant_of || latestRequest.note) ? latestRequest : undefined);
  const interrupted = $derived(
    practice.jobs.some((j) => {
      if (j.concept_id !== conceptId || j.action !== 'generate' || j.purpose || j.processed) return false;
      const turn = app.turn(j.id);
      return turn && turn.status !== 'running' && turn.status !== 'completed';
    }),
  );
  // Exercises come after the lesson: a stepped lesson offers them once its last step is taught.
  const studied = $derived(app.studied(conceptId));

  async function generate() {
    busy = true;
    await app.act(() => api.post('/api/practice/generate', { concept_id: conceptId }));
    busy = false;
  }

  // Ask for different exercises (ADR 0011): new ones replace the exercises the teacher wrote that are not started yet.
  const noteKey = $derived(`different-exercises:${conceptId}`);
  const note = $derived(app.drafts.get(noteKey));
  let differing = $state(false);
  const replaceable = $derived(tasks.filter((t) => t.origin === 'self_created' && t.status === 'pending' && !t.history.length).length);

  async function askDifferent() {
    if (busy) return;
    busy = true;
    const sent = note;
    const result = await app.act(() => api.post('/api/practice/replace', sent.trim() ? { concept_id: conceptId, note: sent } : { concept_id: conceptId }));
    busy = false;
    if (!result) return;
    differing = false;
    if (app.drafts.get(noteKey) === sent) app.drafts.set(noteKey, '');
  }
</script>

{#if tasks.length || earlier.length || generating || (isCurrent && studied)}
  <section class="practice" id="practice" aria-labelledby="practice-title">
    <header>
      <h2 id="practice-title">{t("Practice")}</h2>
      <p>
        {#if tally.total}<strong class="tally">{standing}</strong>{' · '}{/if}{t("Practice is optional before moving on.")}
      </p>
    </header>

    {#if generating}
      <p class="status"><span class="chip"><span class="live-dot"></span>{writingVariant ? t("Writing another exercise") : t("Preparing exercises")}</span></p>
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

    {#if requestFailed && !generating}
      <p class="problem">{t("The new exercises could not be written:")} {diagnostic(requestFailed.error ?? "")}</p>
    {/if}
    {#if tasks.length && !generating}
      {#if differing}
        {#snippet differentHeader()}{replaceable
            ? t("New exercises replace the {count} written by the teacher that you have not started; the rest stay", { count: replaceable })
            : t("New exercises are added; the ones you have started stay")}{/snippet}
        <Composer
          value={note}
          onvalue={(value) => app.drafts.set(noteKey, value)}
          label={t("What should be different")}
          placeholder={t("Optional: what should be different, such as less arithmetic or more on one idea")}
          submitLabel={t("Ask for different exercises")}
          allowEmpty
          disabled={busy}
          onsubmit={askDifferent}
          header={differentHeader}
          onclose={() => (differing = false)}
          closeLabel={t("Cancel")}
          preview={false}
        />
      {:else}
        <button class="btn btn-quiet btn-small different" disabled={busy} onclick={() => (differing = true)}>{t("Ask for different exercises")}</button>
      {/if}
    {/if}

    {#if earlier.length}
      <details class="earlier">
      <summary>{t("Still open in this chapter")} <span>({earlier.length})</span></summary>
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

  .tally {
    color: var(--ink-soft);
    font-weight: 600;
  }

  .earlier-tasks { display: grid; gap: 1rem; margin-top: 1rem; }

  summary {
    cursor: pointer;
    margin-top: 1rem;
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .problem {
    animation: enter-rise var(--settle) var(--ease-out);
    color: var(--danger);
    font-size: var(--step-0);
  }

  .practice > .btn {
    justify-self: start;
  }

  .status {
    animation: enter-fade var(--settle) ease;
  }
</style>
