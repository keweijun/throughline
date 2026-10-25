<script lang="ts">
  import { modEnterToSend, sendKeys } from '../lib/keys';
  import { locale, t, diagnostic } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { autogrow } from '../lib/autogrow';
  import { markdown, hasMath } from '../lib/markdown';
  import { highlights } from '../lib/highlight';
  import { evidenceLabel, helpLabels, solved as isSolved } from '../lib/format';
  import type { Task } from '../lib/types';

  let { task, number, showSection = false }: { task: Task; number?: number; showSection?: boolean } = $props();

  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.task_id === task.id));
  const passages = $derived(mine.map((a) => a.passage));
  const noted = $derived(mine.filter((a) => a.note));

  // The answer is kept as a draft, so it survives moving to another section and back.
  const draftKey = $derived(`exercise:${task.id}`);
  const answer = $derived(app.drafts.get(draftKey));
  const setAnswer = (value: string) => app.drafts.set(draftKey, value);
  let busy = $state(false);
  let confirmSolution = $state(false);
  let preview = $state('');

  $effect(() => {
    const text = answer;
    const timer = setTimeout(() => (preview = hasMath(text) ? text : ''), 150);
    return () => clearTimeout(timer);
  });

  const jobs = $derived((app.state?.practice.jobs ?? []).filter((j) => j.task_id === task.id));
  const working = $derived(jobs.some((j) => app.isRunning(j.id)));
  const latestJob = $derived([...jobs].sort((a, b) => (app.turn(a.id)?.started_at ?? 0) - (app.turn(b.id)?.started_at ?? 0)).at(-1));
  const latestTurn = $derived(latestJob ? app.turn(latestJob.id) : undefined);
  const failedJob = $derived(latestJob && (latestJob.error || (latestTurn && ['failed', 'interrupted', 'paused'].includes(latestTurn.status))) ? latestJob : undefined);
  const submittedAnswer = $derived(latestJob?.action === 'assess' && (!latestJob.processed || latestJob.error) ? latestJob.answer : undefined);
  const lastAssessment = $derived(task.history.filter((h) => h.action === 'assess').at(-1));
  const solved = $derived(isSolved(task));
  const helped = $derived(task.history.some((h) => h.action !== 'assess'));
  const titles = (ids: string[] = []) => ids.map((id) => app.concept(id)?.title ?? id).join(', ');

  const status = $derived.by(() => {
    if (task.status === 'deferred') return { label: t('Saved for later'), tone: 'caution' };
    if (lastAssessment?.kind) {
      const tone = lastAssessment.kind === 'needs_work' ? 'caution' : lastAssessment.kind === 'independent' || lastAssessment.kind === 'retest_passed' ? 'good' : 'accent';
      return { label: evidenceLabel(lastAssessment.kind), tone };
    }
    return null;
  });

  async function act(action: string) {
    if (busy) return;
    busy = true;
    confirmSolution = false;
    const submitted = answer;
    const key = draftKey;
    const result = await app.act(() =>
      api.post(`/api/practice/tasks/${encodeURIComponent(task.id)}/${action}`, action === 'assess' ? { answer: submitted } : {}),
    );
    busy = false;
    // Keep anything typed while the answer was being sent.
    if (result && action === 'assess' && app.drafts.get(key) === submitted) app.drafts.set(key, '');
  }
</script>

<article class="exercise" id="exercise-{task.id}" class:solved aria-label={task.origin === 'review' ? t("Review question") : task.origin === 'chapter_quiz' ? (number ? t('Quiz question {number}', { number }) : t("Quiz question")) : number ? t('Exercise {number}', { number }) : t("Exercise")}>
  <header>
    <span class="label">
      {#if task.origin === 'review'}
        {t("Review question")}
      {:else if task.origin === 'chapter_quiz'}
        {number ? t('Quiz question {number}', { number }) : t("Quiz question")}
        {#if task.from_task_id}
          <span class="origin">· {t("earlier exercise from {section}", { section: titles(task.tests_concept_ids) })}</span>
        {:else}
          <span class="origin">· {t("tests {sections}", { sections: titles(task.tests_concept_ids) })}</span>
        {/if}
      {:else}
        {number ? t('Exercise {number}', { number }) : t("Exercise")}
        <span class="origin">· {task.origin === 'source' ? t("from the course materials") : t("written by the teacher")}</span>
      {/if}
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
            {t(helpLabels[entry.action])}{#if entry.kind}<span class="kind"> · {evidenceLabel(entry.kind)}</span>{/if}
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
        <button class="btn btn-small" onclick={() => setAnswer(submittedAnswer ?? '')}>{t("Restore submitted answer")}</button>
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
      <textarea
        rows="3"
        bind:value={() => answer, setAnswer}
        use:autogrow={answer}
        use:modEnterToSend={() => !busy && answer.trim() && act('assess')}
        placeholder={t("Write your reasoning and answer. Use $…$ for math.")}
        aria-label={t("Exercise answer")}
        aria-describedby="exercise-keys-{task.id}"
      ></textarea>
    </label>
    {#if preview && answer}
      <section class="answer-preview" aria-label={t("Answer preview")}>
        <p class="answer-label">{t("Preview")}</p>
        <div class="prose" use:markdown={{ language: locale.language, text: preview, breaks: true }}></div>
      </section>
    {/if}
    <div class="actions">
      <button class="btn btn-primary" disabled={busy || !answer.trim()} onclick={() => act('assess')}>{t("Check my answer")}</button>
      <span class="keys" id="exercise-keys-{task.id}">{t("{keys} to check · Enter for a new line", { keys: sendKeys })}</span>

      <span class="help">
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('hint')}>{t("Hint")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('steps')}>{t("Key steps")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => (confirmSolution = true)}>{t("Full solution")}</button>
        {#if task.status !== 'deferred' && task.origin !== 'review' && task.origin !== 'chapter_quiz'}
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
    animation: enter-rise var(--settle) var(--ease-out) backwards;
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

  .answer-preview {
    margin-top: -0.4rem;
    padding: 0.6rem 1rem;
    font-size: var(--step-0);
    color: var(--ink-soft);
    border: 1px dashed var(--rule);
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

  .keys {
    font-size: var(--step--1);
    color: var(--pencil);
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
