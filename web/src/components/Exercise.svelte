<script lang="ts">
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import { highlights } from '../lib/highlight';
  import { evidenceLabels, helpLabels } from '../lib/format';
  import type { Task } from '../lib/types';

  let { task, number, showSection = false }: { task: Task; number?: number; showSection?: boolean } = $props();

  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.task_id === task.id));
  const passages = $derived(mine.map((a) => a.passage));
  const noted = $derived(mine.filter((a) => a.note));

  let answer = $state('');
  let busy = $state(false);
  let confirmSolution = $state(false);

  const jobs = $derived((app.state?.practice.jobs ?? []).filter((j) => j.task_id === task.id));
  const working = $derived(jobs.some((j) => app.turn(j.id)?.status === 'running'));
  const latestJob = $derived([...jobs].sort((a, b) => (app.turn(a.id)?.started_at ?? 0) - (app.turn(b.id)?.started_at ?? 0)).at(-1));
  const latestTurn = $derived(latestJob ? app.turn(latestJob.id) : undefined);
  const failedJob = $derived(latestJob && (latestJob.error || (latestTurn && ['failed', 'interrupted', 'paused'].includes(latestTurn.status))) ? latestJob : undefined);
  const submittedAnswer = $derived(latestJob?.action === 'assess' && (!latestJob.processed || latestJob.error) ? latestJob.answer : undefined);
  const lastAssessment = $derived(task.history.filter((h) => h.action === 'assess').at(-1));
  const solved = $derived(lastAssessment?.outcome === 'passed');
  const helped = $derived(task.history.some((h) => h.action !== 'assess'));

  const status = $derived.by(() => {
    if (task.status === 'deferred') return { label: t('Saved for later'), tone: 'caution' };
    if (lastAssessment?.kind) {
      const tone = lastAssessment.kind === 'needs_work' ? 'caution' : lastAssessment.kind === 'independent' ? 'good' : 'accent';
      return { label: diagnostic(evidenceLabels[lastAssessment.kind] ?? lastAssessment.kind), tone };
    }
    return null;
  });

  async function act(action: string) {
    busy = true;
    confirmSolution = false;
    const result = await app.act(() =>
      api.post(`/api/practice/tasks/${encodeURIComponent(task.id)}/${action}`, action === 'assess' ? { answer } : {}),
    );
    busy = false;
    if (result && action === 'assess') answer = '';
  }
</script>

<article class="exercise" id="exercise-{task.id}" class:solved aria-label={number ? t('Exercise {number}', { number }) : t("Exercise")}>
  <header>
    <span class="label">
      {number ? t('Exercise {number}', { number }) : t("Exercise")}
      <span class="origin">· {task.origin === 'source' ? t("from the course materials") : t("written by the teacher")}</span>
      {#if showSection}<span class="origin">· {app.concept(task.concept_id)?.title ?? task.concept_id}</span>{/if}
    </span>
    {#if noted.length}
      <button class="btn btn-quiet btn-small your-notes" onclick={() => app.showAnnotation(noted[0].id)}>
        <span aria-hidden="true">✎</span> {noted.length === 1 ? t("1 note") : t("{count} notes", { count: noted.length })}
      </button>
    {/if}
    {#if status}<span class="chip chip-{status.tone}">{status.label}</span>{/if}
  </header>

  <div class="prose question" data-exercise={task.id} use:highlights={{ passages, text: task.question }} use:markdown={{ language: locale.language, text: task.question, refs: task.source_refs, onSource: (r) => app.openSource(r) }}></div>
  {#if task.source_refs.length}
    <p class="refs">
      {#each task.source_refs as ref}
        <button class="citation" onclick={() => app.openSource(ref)}>{t("View source")}</button>
      {/each}
    </p>
  {/if}

  {#if task.history.length}
    <div class="history">
      {#each task.history as entry, i}
        <details open={i === task.history.length - 1}>
          <summary>
            {diagnostic(helpLabels[entry.action])}{#if entry.kind}<span class="kind"> · {diagnostic(evidenceLabels[entry.kind] ?? entry.kind)}</span>{/if}
          </summary>
          {#if entry.answer}
            <section class="your-answer" aria-label={t("Your answer")}>
              <p class="answer-label">{t("Your answer")}</p>
              <div class="prose" use:markdown={{ language: locale.language, text: entry.answer, breaks: true }}></div>
            </section>
          {/if}
          <section class="teacher-feedback" aria-label={t("Teacher feedback")}>
            <p class="answer-label">{t("Teacher feedback")}</p>
            <div class="prose feedback" data-exercise={task.id} use:highlights={{ passages, text: entry.feedback }} use:markdown={{ language: locale.language, text: entry.feedback, refs: task.source_refs, onSource: (r) => app.openSource(r) }}></div>
          </section>
        </details>
      {/each}
    </div>
  {/if}

  {#if submittedAnswer}
    <section class="your-answer submitted-answer" aria-label={t("Submitted answer")}>
      <p class="answer-label">{t("Submitted answer")}</p>
      <div class="prose" use:markdown={{ language: locale.language, text: submittedAnswer, breaks: true }}></div>
      {#if failedJob}
        <button class="btn btn-small" onclick={() => (answer = submittedAnswer ?? '')}>{t("Restore submitted answer")}</button>
      {/if}
    </section>
  {/if}

  {#if working}
    <p class="working"><span class="chip"><span class="live-dot"></span>{t("The teacher is responding")}</span></p>
  {:else}
    {#if failedJob}
      <p class="problem">{t("The last request did not finish:")} {diagnostic(failedJob.error ?? latestTurn?.error ?? t("The response was interrupted. Please try again."))}</p>
    {/if}
    <label class="field">
      <span class="visually-hidden">{t("Exercise answer")}</span>
      <textarea rows="3" bind:value={answer} placeholder={t("Write your reasoning and answer")} aria-label={t("Exercise answer")}></textarea>
    </label>
    <div class="actions">
      <button class="btn btn-primary" disabled={busy || !answer.trim()} onclick={() => act('assess')}>{t("Check my answer")}</button>
      <span class="help">
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('hint')}>{t("Hint")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('steps')}>{t("Key steps")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => (confirmSolution = true)}>{t("Full solution")}</button>
        {#if task.status !== 'deferred'}
          <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('defer')}>{t("Do later")}</button>
        {/if}
      </span>
    </div>
    {#if confirmSolution}
      <div class="confirm" role="group" aria-label={t("Confirm full solution")}>
        <p>{t("After you see the solution, a correct answer to this exercise counts as solved with help, not on your own.")}</p>
        <div>
          <button class="btn btn-small" onclick={() => act('solution')}>{t("Show the solution")}</button>
          <button class="btn btn-quiet btn-small" onclick={() => (confirmSolution = false)}>{t("Keep trying")}</button>
        </div>
      </div>
    {:else if helped && !solved}
      <p class="note">{t("You've had help on this one, so a correct answer will count as solved with help.")}</p>
    {/if}
  {/if}
</article>

<style>
  .your-notes { margin-left: auto; color: var(--mine); font-weight: 600; }
  .exercise {
    display: grid;
    gap: 0.85rem;
    padding: 1.25rem 1.35rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--sheet);
  }

  .exercise.solved {
    background: transparent;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .label {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .origin {
    font-weight: 400;
    color: var(--pencil);
  }

  .question {
    font-size: var(--step-1);
  }

  .refs {
    margin-top: -0.4rem;
  }

  .refs .citation {
    margin-left: 0;
    font-size: var(--step--1);
  }

  .history {
    display: grid;
    gap: 0.5rem;
    padding-left: 0.9rem;
    border-left: 2px solid var(--accent-wash);
  }

  summary {
    cursor: pointer;
    font-size: var(--step-0);
    font-weight: 500;
    color: var(--accent);
  }

  .kind {
    color: var(--pencil);
    font-weight: 400;
  }

  .your-answer {
    margin-top: 0.4rem;
    font-size: var(--step-0);
    color: var(--ink-soft);
    padding: 0.8rem 1rem;
    background: var(--accent-wash);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
  }

  .answer-label {
    font-weight: 600;
    color: var(--pencil);
    margin-bottom: 0.5rem;
    font-size: var(--step--1);
  }

  .teacher-feedback {
    margin-top: 1rem;
    padding: 0.5rem 0;
  }

  .feedback {
    margin-top: 0.4rem;
    font-size: var(--step-0);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
  }

  .help {
    display: flex;
    flex-wrap: wrap;
    gap: 0.15rem;
  }

  .confirm {
    display: grid;
    gap: 0.5rem;
    padding: 0.75rem 0.9rem;
    border-radius: var(--radius);
    background: var(--caution-wash);
    color: var(--ink);
    font-size: var(--step-0);
  }

  .confirm div {
    display: flex;
    gap: 0.4rem;
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .problem {
    font-size: var(--step-0);
    color: var(--danger);
  }
</style>
