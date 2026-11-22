<script lang="ts">
  import { t, locale } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import CheckQuestion from './CheckQuestion.svelte';
  import Exercise from './Exercise.svelte';
  import type { ReviewSet, Task } from '../lib/types';

  // One review set from before drill sessions (ADR 0014, ADR 0025), kept to read: its questions in order, recall ones
  // answered by choosing, apply ones in writing; one left unanswered can still be answered.
  let { value, collapsed = false }: { value: ReviewSet; collapsed?: boolean } = $props();

  const review = $derived(app.state?.review);
  const all = $derived([...(review?.tasks ?? []), ...(app.state?.practice.tasks ?? []).filter((x) => x.origin === 'chapter_quiz')]);
  const tasks = $derived(value.task_ids.map((id) => all.find((x) => x.id === id)).filter((x): x is Task => !!x));

  const titles = (ids: string[] = []) => ids.map((id) => app.concept(id)?.title ?? id).join(', ');
  const heading = $derived.by(() => {
    if (value.kind === 'chapter_quiz') return t("Chapter quiz · {chapter}", { chapter: app.state?.curriculum.chapters?.find((c) => c.id === value.chapter_id)?.title ?? '' });
    if (value.kind === 'warm_up') return t("Warm-up before {section}", { section: titles([value.concept_id!]) });
    if (value.request) return value.request;
    if (value.scope) return t("Review of {scope}", { scope: scopeLabel() });
    return t("Review for me");
  });
  function scopeLabel() {
    const chapters = (value.scope?.chapter_ids ?? []).map((id) => app.state?.curriculum.chapters?.find((c) => c.id === id)?.title ?? id);
    return [...chapters, titles(value.scope?.concept_ids)].filter(Boolean).join(', ');
  }
  const when = $derived(new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(value.created_at * 1000)));
  const progress = $derived(
    tasks.length ? t("{answered} of {total} answered · {right} right", { answered: value.answered, total: tasks.length, right: value.right }) : '',
  );

</script>

{#snippet questions()}
  {#each tasks as task, i (task.id)}
    {#if task.kind === 'recall' && task.options}
      <CheckQuestion
        check={{ idea: task.idea ?? '', question: task.question, options: task.options, correct: task.correct ?? 0 }}
        answer={task.answer}
        more={false}
        label={t('Review question {number}', { number: i + 1 }) + ' · ' + t("tests {sections}", { sections: titles(task.tests_concept_ids) })}
        onanswer={(choice) => app.answerRecall(task.id, choice)}
        taskId={task.id}
        section={task.concept_id}
      >
        {#snippet after(right: boolean)}
          {#if !right}<button class="btn btn-quiet btn-small revisit" onclick={() => app.revisit(task)}>{t("Revisit")}</button>{/if}
        {/snippet}
      </CheckQuestion>
    {:else}
      <Exercise {task} number={i + 1} />
    {/if}
  {/each}
{/snippet}

<section class="set" class:open={value.open} aria-label={heading}>
  {#if collapsed}
    <details>
      <summary>
        <span class="heading">{heading}</span>
        <span class="meta">{when}{#if progress} · {progress}{/if}</span>
      </summary>
      <div class="questions">{@render questions()}</div>
    </details>
  {:else}
    <header>
      <div>
        <h3 class="heading">{heading}</h3>
        <p class="meta">{when}{#if progress} · {progress}{/if}</p>
      </div>
    </header>
    {#if value.note}<p class="note">{value.note}</p>{/if}
    <div class="questions">{@render questions()}</div>
  {/if}
</section>

<style>
  .set {
    display: grid;
    gap: 0.9rem;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.4rem 1rem;
  }

  .heading {
    font-size: var(--step-1);
    font-weight: 600;
  }

  .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  summary {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.2rem 0.8rem;
    cursor: pointer;
  }

  summary .heading {
    font-size: var(--step-0);
  }

  details .questions {
    margin-top: 1rem;
  }

  .note {
    padding: 0.6rem 0.85rem;
    border-left: 3px solid var(--marker);
    background: var(--raised);
    font-size: var(--step-0);
    color: var(--ink-soft);
  }

  .questions {
    display: grid;
    gap: 1rem;
  }

  .questions :global(.check) {
    margin-top: 0;
  }

  .revisit {
    justify-self: start;
  }



</style>
