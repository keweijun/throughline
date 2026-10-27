<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { CheckAnswer, CheckChoice, CheckQuestion } from '../lib/types';

  // A lesson step's check question (ADR 0009): feedback comes from the explanations the step already returned.
  let {
    lessonId,
    turnId,
    check,
    answer,
    more,
    oncorrect,
  }: { lessonId: string; turnId: string; check: CheckQuestion; answer?: CheckAnswer; more: boolean; oncorrect?: () => void } = $props();

  // Shown at once, before the host has recorded the choice.
  let picked = $state<CheckChoice | null>(null);
  const choice = $derived(answer?.choice ?? picked);
  const right = $derived(check.options[check.correct]);
  const chosen = $derived(typeof choice === 'number' ? check.options[choice] : null);

  async function pick(value: CheckChoice) {
    if (choice !== null) return;
    picked = value;
    if (!(await app.answerCheck(lessonId, turnId, value))) picked = null;
    // A right answer moves straight on; a miss waits so its explanation can be read before the repair.
    else if (value === check.correct && more) oncorrect?.();
  }

  const md = (text: string) => ({ language: locale.language, text });
</script>

<div class="check" role="group" aria-label={t('Check question')}>
  <p class="label">{t('Check question')}</p>
  <div class="prose question" use:markdown={md(check.question)}></div>
  <div class="options">
    {#each check.options as option, index}
      <button
        class="option"
        class:chosen={choice === index}
        class:right={choice !== null && index === check.correct}
        class:wrong={choice === index && index !== check.correct}
        disabled={choice !== null}
        aria-pressed={choice === index}
        aria-label={option.text}
        onclick={() => pick(index)}
      ><span class="prose" use:markdown={md(option.text)}></span></button>
    {/each}
    <button class="option unsure" class:chosen={choice === 'unsure'} disabled={choice !== null} aria-pressed={choice === 'unsure'} onclick={() => pick('unsure')}>
      {t("I'm not sure")}
    </button>
  </div>

  {#if choice !== null}
    <div class="feedback" role="status">
      {#if chosen && choice === check.correct}
        <p class="verdict ok">{t('Correct.')}</p>
        <div class="prose" use:markdown={md(chosen.explanation)}></div>
      {:else}
        {#if chosen}
          <p class="verdict miss">{t('Not quite.')}</p>
          <div class="prose" use:markdown={md(chosen.explanation)}></div>
        {/if}
        <p class="verdict">{t('The answer:')}</p>
        <div class="prose" use:markdown={md(right.text + '\n\n' + right.explanation)}></div>
        {#if more}<p class="hint">{t('The next step starts by going over this.')}</p>{/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .check {
    display: grid;
    gap: 0.6rem;
    margin-top: 1.75rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--rule);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
    background: var(--sheet);
    font-size: var(--step-0);
  }

  .label {
    margin: 0;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .check :global(.prose p) {
    margin: 0;
  }

  .options {
    display: grid;
    gap: 0.4rem;
  }

  .option {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .option:hover:not(:disabled) {
    border-color: var(--accent);
  }

  .option:disabled {
    cursor: default;
  }

  .option.unsure {
    color: var(--ink-soft);
    font-style: italic;
  }

  .option.chosen {
    border-color: var(--accent);
    background: var(--accent-wash);
  }

  .option.right {
    border-color: var(--good);
    background: var(--good-wash);
  }

  .option.wrong {
    border-color: var(--danger);
    background: var(--danger-wash);
  }

  .feedback {
    display: grid;
    gap: 0.4rem;
    padding-top: 0.4rem;
    border-top: 1px solid var(--rule);
  }

  .verdict {
    margin: 0;
    font-weight: 600;
  }

  .verdict.ok {
    color: var(--good);
  }

  .verdict.miss {
    color: var(--danger);
  }

  .hint {
    margin: 0;
    font-size: var(--step--1);
    color: var(--pencil);
  }
</style>
