<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import type { Chapter, Task } from '../lib/types';
  import Exercise from './Exercise.svelte';

  /**
   * Drill this chapter (ADR 0025): a drill session scoped to the chapter, as the chapter quiz was, held in the Review
   * place. Quizzes taken before stay here to read, and any question left unanswered can still be answered.
   */
  let { chapter }: { chapter: Chapter } = $props();

  let busy = $state(false);
  const answered = (task: Task) => task.history.some((h) => h.action === 'assess');
  const quizzes = $derived.by(() => {
    const groups = new Map<string, Task[]>();
    for (const task of app.quizTasks(chapter.id)) {
      const key = task.quiz_id ?? task.id;
      groups.set(key, [...(groups.get(key) ?? []), task]);
    }
    return [...groups.entries()].map(([id, tasks]) => ({ id, tasks }));
  });
  const score = (tasks: Task[]) => ({ answered: tasks.filter(answered).length, passed: tasks.filter(solved).length, total: tasks.length });

  async function drill() {
    if (busy) return;
    busy = true;
    await app.startDrill({ kind: 'chapter', chapter_id: chapter.id });
    busy = false;
  }
</script>

<section class="quiz" aria-labelledby="drill-title">
  <!-- What it is on the left, starting it on the right. -->
  <div class="start">
    <div>
      <h2 id="drill-title">{t("Drill this chapter")}</h2>
      <p class="note">{t("A few of this chapter's earlier exercises asked again, with new questions that span it. Answer from memory: each answer counts for the sections it tests. It opens in Review.")}</p>
    </div>
    <button class="btn" disabled={busy} onclick={drill}>{t("Start a drill")}</button>
  </div>

  {#if quizzes.length}
    <details class="past">
      <summary>{t("Earlier quizzes")} <span>({quizzes.length})</span></summary>
      {#each quizzes as quiz, n (quiz.id)}
        <div class="earlier-quiz">
          <p class="progress">{t("Quiz {number}: {passed} of {total} passed", { number: n + 1, ...score(quiz.tasks) })}</p>
          {#each quiz.tasks as task, i (task.id)}
            <Exercise {task} number={i + 1} />
          {/each}
        </div>
      {/each}
    </details>
  {/if}
</section>

<style>
  .quiz {
    display: grid;
    gap: 1rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  .start {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem 1.5rem;
  }

  .start > div {
    flex: 1 1 20rem;
  }

  .note {
    margin-top: 0.25rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .progress {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
  }

  summary {
    cursor: pointer;
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .earlier-quiz {
    display: grid;
    gap: 1rem;
    margin-top: 1rem;
  }
</style>
