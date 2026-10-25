<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { solved } from '../lib/format';
  import type { Chapter, Task } from '../lib/types';
  import Exercise from './Exercise.svelte';

  let { chapter }: { chapter: Chapter } = $props();

  let busy = $state(false);

  const answered = (task: Task) => task.history.some((h) => h.action === 'assess');
  const all = $derived(app.quizTasks(chapter.id));
  // Each request makes one quiz; the newest is the current one.
  const quizzes = $derived.by(() => {
    const groups = new Map<string, Task[]>();
    for (const task of all) {
      const key = task.quiz_id ?? task.id;
      groups.set(key, [...(groups.get(key) ?? []), task]);
    }
    return [...groups.entries()].map(([id, tasks]) => ({ id, tasks }));
  });
  const current = $derived(quizzes.at(-1));
  const past = $derived(quizzes.slice(0, -1));
  // A new quiz waits until every question asked so far has an answer.
  const open = $derived(all.some((task) => !answered(task)));
  const jobs = $derived(
    (app.state?.practice.jobs ?? [])
      .filter((j) => j.purpose === 'chapter_quiz' && j.chapter_id === chapter.id)
      .sort((a, b) => (app.turn(a.id)?.started_at ?? 0) - (app.turn(b.id)?.started_at ?? 0)),
  );
  const preparing = $derived(jobs.some((j) => app.isRunning(j.id)));
  // The newest request when it made no quiz: it failed, or stopped before it finished.
  const problem = $derived.by(() => {
    const last = jobs.at(-1);
    if (!last || app.isRunning(last.id) || quizzes.some((q) => q.id === last.id)) return null;
    if (last.error) return { error: last.error };
    const turn = app.turn(last.id);
    return turn && turn.status !== 'completed' ? { error: null } : null;
  });
  const score = (tasks: Task[]) => ({ answered: tasks.filter(answered).length, passed: tasks.filter(solved).length, total: tasks.length });

  async function take() {
    if (busy) return;
    busy = true;
    await app.takeQuiz(chapter.id);
    busy = false;
  }
</script>

<section class="quiz" aria-labelledby="quiz-title">
  <h2 id="quiz-title">{t("Chapter quiz")}</h2>
  <p class="note">
    {t("A few earlier exercises from this chapter mixed with new questions that span it. Answer from memory: each answer counts as a review of the sections it tests. Optional.")}
  </p>

  {#if current}
    <p class="progress" id="quiz-progress">{t("{answered} of {total} answered, {passed} passed", score(current.tasks))}</p>
    {#each current.tasks as task, i (task.id)}
      <Exercise {task} number={i + 1} />
    {/each}
  {/if}

  {#if preparing}
    <p class="status"><span class="chip"><span class="live-dot"></span>{t("Preparing the quiz")}</span></p>
  {:else}
    {#if problem}
      <p class="problem">
        {#if problem.error}{t("The quiz could not be prepared:")} {diagnostic(problem.error)}{:else}{t("Preparing the quiz stopped before it finished.")}{/if}
      </p>
    {/if}
    {#if !open}
      <div>
        <button class="btn" class:btn-primary={!current} disabled={busy} onclick={take}>
          {problem ? t("Try again") : current ? t("Take the quiz again") : t("Take the chapter quiz")}
        </button>
      </div>
    {/if}
  {/if}

  {#if past.length}
    <details class="past">
      <summary>{t("Earlier quizzes")} <span>({past.length})</span></summary>
      {#each past as quiz, n (quiz.id)}
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

  .note {
    margin-top: -0.7rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .progress {
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
  }

  .problem {
    color: var(--danger);
    font-size: var(--step-0);
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
