<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { questionId, replyText, studio, type AsyncQuestion } from '../lib/studio.svelte';

  /**
   * Questions Codex asks in a message, as Codex's app shows them (its async user input): each with its options to
   * click and a line for an answer in the learner's own words. The answers go back as a message, which starts Codex's
   * next turn, or joins the running one. Answered questions show their answer; only the latest turn's can be answered.
   */
  let { item, questions, current }: { item: string; questions: AsyncQuestion[]; current: boolean } = $props();

  const ids = $derived(questions.map((_, i) => questionId(item, i)));
  const given = $derived(ids.map((id) => studio.replies.get(id)));
  const open = $derived(current && given.some((g) => g === undefined));
  const chosen: Record<number, string> = $state({});
  const other: Record<number, string> = $state({});
  let busy = $state(false);

  const answer = (i: number) => (chosen[i] === '__other' ? other[i]?.trim() : chosen[i]) ?? '';
  const ready = $derived(questions.some((_, i) => given[i] === undefined && answer(i)));

  async function reply(event: SubmitEvent) {
    event.preventDefault();
    if (busy || !ready) return;
    const replies = questions.flatMap((question, i) =>
      given[i] === undefined && answer(i) ? [{ questionItemId: ids[i], question: question.title, answer: answer(i) }] : [],
    );
    busy = true;
    try {
      await studio.send({ text: replyText(replies), elements: [], skills: [], mentions: [], images: [] });
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    busy = false;
  }
</script>

<form class="questions" class:open aria-label={t('Codex has a question')} onsubmit={reply}>
  {#each questions as question, i (i)}
    <fieldset disabled={!open || given[i] !== undefined}>
      <legend>{question.title}</legend>
      {#if given[i] !== undefined}
        <p class="given">{given[i]}</p>
      {:else if open}
        {#each question.options ?? [] as option (option)}
          <label class="option">
            <input type="radio" name={`q-${item}-${i}`} value={option} bind:group={chosen[i]} />
            <span>{option}</span>
          </label>
        {/each}
        <input
          class="answer"
          type="text"
          aria-label={question.title}
          placeholder={question.options?.length ? t('Something else') : t('Your answer')}
          bind:value={other[i]}
          oninput={() => other[i]?.trim() && (chosen[i] = '__other')}
        />
      {:else}
        <p class="given">{t('Not answered')}</p>
      {/if}
    </fieldset>
  {/each}
  {#if open}
    <div class="actions"><button class="btn btn-small btn-primary" disabled={busy || !ready}>{t('Answer')}</button></div>
  {/if}
</form>

<style>
  .questions {
    display: grid;
    gap: 0.6rem;
    padding: 0.7rem 0.8rem;
    border: 1px solid var(--rule);
    border-radius: calc(var(--radius) * 2);
    font-size: var(--step--1);
  }

  .questions.open {
    border-color: var(--caution);
    background: var(--caution-wash);
  }

  fieldset {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    margin-bottom: 0.35rem;
    font-weight: 600;
  }

  .option {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    cursor: pointer;
  }

  .given {
    margin: 0;
    color: var(--ink-soft);
  }

  .answer {
    font-size: var(--step--1);
  }

  /* The answer button on the right, where the learner's eye ends after the last question. */
  .actions {
    display: flex;
    justify-content: flex-end;
  }
</style>
