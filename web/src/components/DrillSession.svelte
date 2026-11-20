<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { DrillSession, Task } from '../lib/types';
  import CheckQuestion from './CheckQuestion.svelte';
  import Composer from './Composer.svelte';
  import Exercise from './Exercise.svelte';

  /**
   * One drill session (ADR 0025): what the learner said, the fast teacher's replies and the questions each one set,
   * answered in place. It goes on for as long as the learner likes and is never finished: More questions, or say what to
   * drill next.
   */
  let { session }: { session: DrillSession } = $props();

  // In the session's order, turn by turn: task ids start with their turn's id, which says nothing of when it came.
  const tasks = $derived.by(() => {
    const mine = new Map((app.state?.review.tasks ?? []).filter((x) => x.session_id === session.id).map((x) => [x.id, x]));
    return session.task_ids.map((id) => mine.get(id)).filter((x) => !!x);
  });
  const turns = $derived(session.turn_ids.map((id) => app.turn(id)).filter((turn) => !!turn));
  const replying = $derived(turns.some((turn) => turn.status === 'running'));
  const stopped = $derived(turns.at(-1) && !['running', 'completed'].includes(turns.at(-1)!.status));
  const titles = (ids: string[] = []) => ids.map((id) => app.concept(id)?.title ?? id).join(', ');
  const draftKey = $derived(`drill:${session.id}`);
  const draft = $derived(app.drafts.get(draftKey));
  let busy = $state(false);
  // Questions are numbered through the session, so a reply can refer to one.
  const numbers = $derived(new Map(tasks.map((task, i) => [task.id, i + 1])));

  async function send(message = '') {
    if (busy || replying) return;
    busy = true;
    const sent = draft;
    const result = await app.sendDrill(session.id, message);
    busy = false;
    if (result && message && app.drafts.get(draftKey) === sent) app.drafts.set(draftKey, '');
  }
</script>

{#snippet question(task: Task)}
  {#if task.kind === 'recall' && task.options}
    <CheckQuestion
      check={{ idea: task.idea ?? '', question: task.question, options: task.options, correct: task.correct ?? 0 }}
      answer={task.answer}
      more={false}
      label={t('Question {number}', { number: numbers.get(task.id) ?? 0 }) + ' · ' + t("tests {sections}", { sections: titles(task.tests_concept_ids) })}
      onanswer={(choice) => app.answerRecall(task.id, choice)}
      taskId={task.id}
      section={task.concept_id}
    >
      {#snippet after(right: boolean)}
        {#if !right}<button class="btn btn-quiet btn-small" onclick={() => app.revisit(task)}>{t("Revisit")}</button>{/if}
      {/snippet}
    </CheckQuestion>
  {:else}
    <Exercise {task} number={numbers.get(task.id)} />
  {/if}
{/snippet}

<section class="drill" aria-label={t("Drill session")}>
  {#each turns as turn (turn.id)}
    {@const said = session.messages?.[turn.id]}
    {#if said}<p class="said">{said}</p>{/if}
    {#if turn.text}
      <div class="prose reply" use:markdown={{ language: locale.language, text: turn.text, streaming: turn.status === 'running' }}></div>
    {:else if turn.status === 'running'}
      <p class="status"><span class="chip"><span class="live-dot"></span>{t("The teacher is choosing questions")}</span></p>
    {/if}
    {#each tasks.filter((task) => task.drill_turn_id === turn.id) as task (task.id)}
      {@render question(task)}
    {/each}
  {/each}
  {#if stopped}<p class="problem">{t("The teacher's reply stopped before it finished. Ask again.")}</p>{/if}

  <div class="next">
    <button class="btn btn-primary" disabled={busy || replying} onclick={() => send()}>{t("More questions")}</button>
    <Composer
      id="drill-message-{session.id}"
      value={draft}
      onvalue={(value) => app.drafts.set(draftKey, value)}
      label={t("Message to the teacher")}
      placeholder={t("Ask about an answer, or say what to drill next")}
      submitLabel={t("Send")}
      disabled={busy || replying}
      onsubmit={() => send(draft)}
      preview={false}
    />
  </div>
</section>

<style>
  .drill {
    display: grid;
    gap: 1.25rem;
  }

  .said {
    justify-self: end;
    max-width: 85%;
    padding: 0.55rem 0.85rem;
    border-radius: var(--radius);
    background: var(--accent-wash);
    font-size: var(--step-0);
    white-space: pre-wrap;
  }

  .reply {
    font-size: var(--step-0);
    line-height: 1.6;
  }

  .status {
    font-size: var(--step--1);
  }

  .problem {
    font-size: var(--step--1);
    color: var(--danger, var(--accent));
  }

  .next {
    display: grid;
    gap: 0.75rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--rule);
  }

  .next > .btn {
    justify-self: start;
  }
</style>
