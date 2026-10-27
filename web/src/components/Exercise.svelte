<script lang="ts">
  import { modEnterToSend, sendKeys } from '../lib/keys';
  import { locale, t, diagnostic, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { autogrow } from '../lib/autogrow';
  import { markdown, hasMath } from '../lib/markdown';
  import { highlights } from '../lib/highlight';
  import { evidenceLabel, helpLabels, partLabels, partStatuses, solved as isSolved } from '../lib/format';
  import type { SkipReason, Task } from '../lib/types';
  import AnswerImages from './AnswerImages.svelte';

  let { task, number, showSection = false }: { task: Task; number?: number; showSection?: boolean } = $props();

  const mine = $derived((app.state?.annotations ?? []).filter((a) => a.task_id === task.id));
  const passages = $derived(mine.map((a) => a.passage));
  const noted = $derived(mine.filter((a) => a.note));

  // The answer is kept as a draft, so it survives moving to another section and back.
  const draftKey = $derived(`exercise:${task.id}`);
  const answer = $derived(app.drafts.get(draftKey));
  const setAnswer = (value: string) => app.drafts.set(draftKey, value);
  // Attached images are uploaded at once and kept, by name, as part of the draft.
  const imagesKey = $derived(`exercise-images:${task.id}`);
  const readImages = (key: string): string[] => {
    try {
      return JSON.parse(app.drafts.get(key) || '[]');
    } catch {
      return [];
    }
  };
  const images = $derived(readImages(imagesKey));
  const setImages = (value: string[]) => app.drafts.set(imagesKey, value.length ? JSON.stringify(value) : '');
  const IMAGE_TYPES = 'image/png,image/jpeg,image/gif,image/webp';
  let uploading = $state(0);
  let picker = $state<HTMLInputElement>();

  async function attach(files: File[]) {
    const key = imagesKey;
    for (const file of files.filter((f) => f.type.startsWith('image/'))) {
      uploading += 1;
      const result = await app.act(() => api.upload<{ image: string }>('/api/practice/images', file));
      uploading -= 1;
      const current = readImages(key);
      if (result && !current.includes(result.image)) app.drafts.set(key, JSON.stringify([...current, result.image]));
    }
  }

  function pasteImages(event: ClipboardEvent) {
    const files = [...(event.clipboardData?.files ?? [])].filter((f) => f.type.startsWith('image/'));
    if (!files.length) return;
    event.preventDefault();
    void attach(files);
  }

  // A question about the exercise has its own draft: asking is never assessed (ADR 0011).
  const askKey = $derived(`exercise-ask:${task.id}`);
  const question = $derived(app.drafts.get(askKey));
  let asking = $state(false);
  let busy = $state(false);
  const canCheck = $derived(!busy && !uploading && (answer.trim() !== '' || images.length > 0));
  let confirmSolution = $state(false);
  let confirmSkip = $state(false);
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
  const submittedJob = $derived(latestJob?.action === 'assess' && (!latestJob.processed || latestJob.error) ? latestJob : undefined);
  const submittedQuestion = $derived(latestJob?.action === 'ask' && (!latestJob.processed || latestJob.error) ? latestJob.question : undefined);
  const lastAssessment = $derived(task.history.filter((h) => h.action === 'assess').at(-1));
  const solved = $derived(isSolved(task));
  // Parts are assessed one by one and accumulate across answers (ADR 0011).
  const parts = $derived(partStatuses(task));
  const partName = (i: number) => {
    const part = task.parts?.[i];
    return (typeof part === 'object' && part.label) || t('Part {number}', { number: i + 1 });
  };
  const partsCorrect = (statuses: string[]) => ({ correct: statuses.filter((s) => s === 'correct').length, total: statuses.length });
  const helped = $derived(task.history.some((h) => h.action !== 'assess' && h.action !== 'ask'));
  // Only a section's own exercises are skipped (ADR 0011); review and quiz questions are not.
  const skippable = $derived((task.origin === 'source' || task.origin === 'self_created') && task.status !== 'skipped' && !solved);
  const skipReasons: Record<SkipReason, MessageKey> = { too_easy: 'Too easy', too_tedious: 'Too tedious', not_relevant: 'Not relevant' };
  // A part split from a homework question shows the question and where its other parts are taught (ADR 0012).
  const homework = $derived(task.exercise ? app.concept(task.concept_id)?.exercises?.find((e) => e.question === task.exercise && e.part_of) : undefined);
  const titles = (ids: string[] = []) => ids.map((id) => app.concept(id)?.title ?? id).join(', ');

  const status = $derived.by(() => {
    if (task.status === 'deferred') return { label: t('Saved for later'), tone: 'caution' };
    if (task.status === 'skipped') return { label: task.skip_reason ? t('Skipped · {reason}', { reason: t(skipReasons[task.skip_reason]) }) : t('Skipped'), tone: 'plain' };
    if (lastAssessment && parts.length > 1 && !solved) return { label: t('{correct}/{total} parts correct', partsCorrect(parts)), tone: 'caution' };
    if (lastAssessment?.kind) {
      const tone = lastAssessment.kind === 'needs_work' ? 'caution' : lastAssessment.kind === 'independent' || lastAssessment.kind === 'retest_passed' ? 'good' : 'accent';
      return { label: evidenceLabel(lastAssessment.kind), tone };
    }
    return null;
  });

  async function act(action: string, body: { reason?: string } = {}) {
    if (busy) return;
    busy = true;
    confirmSolution = false;
    confirmSkip = false;
    const submitted = answer;
    const attached = images;
    const key = draftKey;
    const imageKey = imagesKey;
    const sent = action !== 'assess' ? body : attached.length ? { answer: submitted, images: attached } : { answer: submitted };
    const result = await app.act(() => api.post(`/api/practice/tasks/${encodeURIComponent(task.id)}/${action}`, sent));
    busy = false;
    // Keep anything typed or attached while the answer was being sent.
    if (result && action === 'assess' && app.drafts.get(key) === submitted) app.drafts.set(key, '');
    if (result && action === 'assess' && JSON.stringify(readImages(imageKey)) === JSON.stringify(attached)) app.drafts.set(imageKey, '');
  }

  function restoreSubmitted() {
    setAnswer(submittedJob?.answer ?? '');
    setImages(submittedJob?.images ?? []);
  }

  async function ask() {
    if (busy || !question.trim()) return;
    busy = true;
    const submitted = question;
    const key = askKey;
    const result = await app.act(() => api.post(`/api/practice/tasks/${encodeURIComponent(task.id)}/ask`, { question: submitted }));
    busy = false;
    if (!result) return;
    asking = false;
    if (app.drafts.get(key) === submitted) app.drafts.set(key, '');
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

  <div class="prose question" data-exercise={task.id} use:highlights={{ passages, text: task.question }} use:markdown={{ language: locale.language, text: task.question, breaks: true, refs: task.source_refs, onSource: (r) => app.openSource(r) }}></div>
  {#if homework}
    <div class="homework">
      <p>{t('{part}, a part of {question}', { part: homework.question!, question: homework.part_of! })}</p>
      {#if homework.other_parts?.length}
        <ul aria-label={t("Other parts")}>
          {#each homework.other_parts as part}
            {@const section = part.concept_id ? app.concept(part.concept_id) : undefined}
            <li>
              {part.question} ·
              {#if section}
                {t("taught in")} <button class="link" onclick={() => app.view(section.id)}>{section.title}</button>
              {:else}
                <span class="waiting">{t("waiting for a later chapter")}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
  {#if task.source_refs.length}
    <p class="refs">
      {#each task.source_refs as ref}
        <button class="citation" onclick={() => app.openSource(ref)}>{t("View source")}</button>
      {/each}
    </p>
  {/if}

  {#if lastAssessment && parts.length > 1}
    <ol class="parts" aria-label={t("Parts")}>
      {#each parts as status, i}
        <li>
          <span class="part-name">{partName(i)}</span>
          <span class="chip chip-{partLabels[status].tone}">{t(partLabels[status].label)}</span>
        </li>
      {/each}
    </ol>
  {/if}

  {#if task.history.length}
    <div class="history">
      {#each task.history as entry, i}
        <details open={i === task.history.length - 1}>
          <summary>
            {t(helpLabels[entry.action])}{#if entry.parts && entry.parts.length > 1 && entry.outcome !== 'passed'}<span class="kind"> · {t('{correct}/{total} parts correct', partsCorrect(entry.parts))}</span>{:else if entry.kind}<span class="kind"> · {evidenceLabel(entry.kind)}</span>{/if}
          </summary>
          {#if entry.question}
            <section class="your-answer" aria-label={t("Your question")}>
              <p class="answer-label">{t("Your question")}</p>
              <div class="prose" use:markdown={{ language: locale.language, text: entry.question, breaks: true }}></div>
            </section>
          {/if}
          {#if entry.answer || entry.images?.length}
            <section class="your-answer" aria-label={t("Your answer")}>
              <p class="answer-label">{t("Your answer")}</p>
              {#if entry.answer}<div class="prose" use:markdown={{ language: locale.language, text: entry.answer, breaks: true }}></div>{/if}
              <AnswerImages images={entry.images ?? []} />
            </section>
          {/if}
          <section class="teacher-feedback" aria-label={entry.action === 'ask' ? t("Teacher's answer") : t("Teacher feedback")}>
            <p class="answer-label">{entry.action === 'ask' ? t("Teacher's answer") : t("Teacher feedback")}</p>
            <div class="prose feedback" data-exercise={task.id} use:highlights={{ passages, text: entry.feedback }} use:markdown={{ language: locale.language, text: entry.feedback, refs: task.source_refs, onSource: (r) => app.openSource(r) }}></div>
          </section>
        </details>
      {/each}
    </div>
  {/if}

  {#if submittedJob}
    <section class="your-answer submitted-answer" aria-label={t("Submitted answer")}>
      <p class="answer-label">{t("Submitted answer")}</p>
      {#if submittedJob.answer}<div class="prose" use:markdown={{ language: locale.language, text: submittedJob.answer, breaks: true }}></div>{/if}
      <AnswerImages images={submittedJob.images ?? []} />
      {#if failedJob}
        <button class="btn btn-small" onclick={restoreSubmitted}>{t("Restore submitted answer")}</button>
      {/if}
    </section>
  {/if}

  {#if submittedQuestion}
    <section class="your-answer submitted-answer" aria-label={t("Your question")}>
      <p class="answer-label">{t("Your question")}</p>
      <div class="prose" use:markdown={{ language: locale.language, text: submittedQuestion, breaks: true }}></div>
      {#if failedJob}
        <button class="btn btn-small" onclick={() => { app.drafts.set(askKey, submittedQuestion ?? ''); asking = true; }}>{t("Restore question")}</button>
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
        use:modEnterToSend={() => canCheck && act('assess')}
        onpaste={pasteImages}
        placeholder={t("Write your reasoning and answer, or paste or attach images of your work. Use $…$ for math.")}
        aria-label={t("Exercise answer")}
        aria-describedby="exercise-keys-{task.id}"
      ></textarea>
    </label>
    <AnswerImages {images} onremove={(name) => setImages(images.filter((n) => n !== name))} />
    {#if preview && answer}
      <section class="answer-preview" aria-label={t("Answer preview")}>
        <p class="answer-label">{t("Preview")}</p>
        <div class="prose" use:markdown={{ language: locale.language, text: preview, breaks: true }}></div>
      </section>
    {/if}
    <div class="actions">
      <button class="btn btn-primary" disabled={!canCheck} onclick={() => act('assess')}>{t("Check my answer")}</button>
      <input
        bind:this={picker}
        class="visually-hidden"
        type="file"
        accept={IMAGE_TYPES}
        multiple
        tabindex="-1"
        aria-label={t("Choose images of your work")}
        onchange={(e) => {
          const input = e.currentTarget;
          void attach([...(input.files ?? [])]);
          input.value = '';
        }}
      />
      <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => picker?.click()}>
        {uploading ? t("Attaching…") : t("Attach image")}
      </button>
      <span class="keys" id="exercise-keys-{task.id}">{t("{keys} to check · Enter for a new line", { keys: sendKeys })}</span>

      <span class="help">
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('hint')}>{t("Hint")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('steps')}>{t("Key steps")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => ((confirmSolution = true), (confirmSkip = false))}>{t("Full solution")}</button>
        <button class="btn btn-quiet btn-small" disabled={busy} aria-expanded={asking} onclick={() => (asking = !asking)}>{t("Ask about this")}</button>
        {#if task.status !== 'deferred' && task.origin !== 'review' && task.origin !== 'chapter_quiz'}
          <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => act('defer')}>{t("Do later")}</button>
        {/if}
        {#if skippable}
          <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => ((confirmSkip = true), (confirmSolution = false))}>{t("Skip")}</button>
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
    {:else if confirmSkip}
      <div class="confirm" role="group" aria-label={t("Skip this exercise")}>
        <p>{t("A skipped exercise is closed: it is not counted as open and does not come back later. Why skip it?")}</p>
        <div>
          {#each Object.entries(skipReasons) as [reason, label]}
            <button class="btn btn-small" onclick={() => act('skip', { reason })}>{t(label)}</button>
          {/each}
          <button class="btn btn-small" onclick={() => act('skip')}>{t("Skip without a reason")}</button>
          <button class="btn btn-quiet btn-small" onclick={() => (confirmSkip = false)}>{t("Cancel")}</button>
        </div>
      </div>
    {:else if helped && !solved}
      <p class="note">{t("You've had help on this one, so a correct answer will count as solved with help.")}</p>
    {/if}
    {#if asking}
      <div class="ask" role="group" aria-label={t("Ask about this")}>
        <textarea
          rows="2"
          bind:value={() => question, (v: string) => app.drafts.set(askKey, v)}
          use:autogrow={question}
          use:modEnterToSend={ask}
          placeholder={t("What does this exercise or one of its parts mean?")}
          aria-label={t("Question about this exercise")}
        ></textarea>
        <div>
          <button class="btn btn-primary btn-small" disabled={busy || !question.trim()} onclick={ask}>{t("Ask")}</button>
          <button class="btn btn-quiet btn-small" onclick={() => (asking = false)}>{t("Cancel")}</button>
          <span class="keys">{t("{keys} to ask", { keys: sendKeys })} · {t("Asking is never graded.")}</span>
        </div>
      </div>
    {/if}
  {/if}
</article>

<style>
  .your-notes { margin-left: auto; color: var(--mine); font-weight: 600; }
  .exercise {
    animation: enter-rise var(--settle) var(--ease-out) backwards;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
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

  .homework {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .homework p,
  .homework ul {
    margin: 0;
  }

  .homework ul {
    padding-left: 1.2rem;
  }

  .homework .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
  }

  .homework .link:hover {
    text-decoration: underline;
  }

  .refs .citation {
    margin-left: 0;
    font-size: var(--step--1);
  }

  .parts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1rem;
    margin: -0.2rem 0 0;
    padding: 0;
    list-style: none;
    font-size: var(--step--1);
  }

  .parts li {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .part-name {
    color: var(--pencil);
  }

  .history {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
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

  /* A long inline formula cannot wrap, so learner text scrolls within its block. */
  .answer-preview .prose,
  .your-answer .prose {
    overflow-x: auto;
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
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .ask {
    display: grid;
    gap: 0.5rem;
  }

  .ask div {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
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
