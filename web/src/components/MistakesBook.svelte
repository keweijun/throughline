<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { Mistake } from '../lib/types';

  /**
   * The mistakes book (issue #219): what the learner missed, newest first, each with what they answered and the feedback.
   * Nothing is counted or cleared: an entry they later got right stays, folded below with when.
   */
  let { entries, onretry }: { entries: Mistake[]; onretry?: (entry: Mistake) => void } = $props();

  const open = $derived(entries.filter((e) => !e.right_at));
  const right = $derived(entries.filter((e) => e.right_at));
  const md = (text: string) => ({ language: locale.language, text });
  const date = (at: number | null) => (at ? new Intl.DateTimeFormat(locale.language, { dateStyle: 'medium' }).format(new Date(at * 1000)) : '');
  const kinds = { exercise: "Exercise", quiz: "Chapter quiz", review: "Review question", check: "Check questions" } as const;
  const sections = (entry: Mistake) => entry.concept_ids.map((id) => app.concept(id)?.title ?? id).join(', ');
  // The exercise, quiz question or lesson step it came from; a review question stays with its set on this page.
  const linked = (entry: Mistake) => (entry.kind === 'check' ? !!entry.turn_id && !!app.turn(entry.turn_id) : entry.kind !== 'review' && !!entry.task_id);

  function go(entry: Mistake) {
    if (entry.kind === 'check') app.showLesson(entry.turn_id!);
    else app.showTask(entry.task_id!);
  }
</script>

{#snippet item(entry: Mistake)}
  <li class="mistake" class:right={!!entry.right_at}>
    <p class="meta">
      <span class="kind">{t(kinds[entry.kind])}</span>
      <span>{sections(entry)}</span>
      {#if entry.right_at}<span class="chip chip-good">{t("Got right {date}", { date: date(entry.right_at) })}</span>
      {:else if entry.last_missed_at}<span>{t("Missed {date}", { date: date(entry.last_missed_at) })}</span>{/if}
    </p>
    {#if entry.kind === 'check'}
      <p class="idea">{entry.idea}</p>
    {/if}
    <div class="prose question" use:markdown={md(entry.question)}></div>
    {#if entry.part}<div class="prose part" use:markdown={md(entry.part)}></div>{/if}
    {#if entry.feedback !== undefined}
      <details>
        <summary>{t("Your answer and the feedback")}</summary>
        {#if entry.answer}<div class="prose answer" use:markdown={md(entry.answer)}></div>{/if}
        <div class="prose feedback" use:markdown={md(entry.feedback)}></div>
      </details>
    {:else}
      <dl>
        <dt>{t("You chose")}</dt>
        <dd class="prose" use:markdown={md(entry.chosen ?? t("I'm not sure"))}></dd>
        <dt>{t("Answer")}</dt>
        <dd class="prose" use:markdown={md(entry.correct_answer ?? '')}></dd>
        {#if entry.why}<dt>{t("Why")}</dt><dd class="prose" use:markdown={md(entry.why)}></dd>{/if}
      </dl>
    {/if}
    {#if linked(entry) || onretry}
      <p class="actions">
        {#if linked(entry)}<button class="link" onclick={() => go(entry)}>{entry.kind === 'check' ? t("Go to the lesson step") : t("Go to the question")}</button>{/if}
        {#if onretry}<button class="link" onclick={() => onretry(entry)}>{t("Try it again")}</button>{/if}
      </p>
    {/if}
  </li>
{/snippet}

<section class="book" aria-labelledby="mistakes-title">
  <!-- The Review place's tab already says Mistakes; the heading names the region for assistive technology only. -->
  <h2 id="mistakes-title" class="visually-hidden">{t("Mistakes")}</h2>
  {#if !entries.length}
    <p class="note">{t("Exercise parts you miss, wrong review answers and check questions you miss more than once collect here.")}</p>
  {:else}
    {#if open.length}
      <ol>
        {#each open as entry (entry.id)}{@render item(entry)}{/each}
      </ol>
    {:else}
      <p class="note">{t("You have since got every one of these right.")}</p>
    {/if}
    {#if right.length}
      <details class="since" open={!open.length}>
        <summary>{t("Since got right")}</summary>
        <ol>
          {#each right as entry (entry.id)}{@render item(entry)}{/each}
        </ol>
      </details>
    {/if}
  {/if}
</section>

<style>
  .book {
    display: grid;
    gap: 1rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  ol {
    display: grid;
    gap: 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .mistake {
    display: grid;
    gap: 0.5rem;
    padding: 0.85rem 1.1rem;
    border: 1px solid var(--rule);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .mistake.right {
    border-left-color: var(--rule-strong);
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem 0.75rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .kind {
    font-weight: 600;
    color: var(--ink-soft);
  }

  .idea {
    font-weight: 600;
    font-size: var(--step-0);
  }

  .question,
  .part {
    font-size: var(--step-0);
    line-height: 1.55;
  }

  details summary {
    font-size: var(--step--1);
    color: var(--accent);
    cursor: pointer;
  }

  details > .prose {
    margin-top: 0.6rem;
    font-size: var(--step--1);
    line-height: 1.55;
  }

  .answer {
    padding-left: 0.75rem;
    border-left: 2px solid var(--rule);
    color: var(--ink-soft);
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
    align-items: baseline;
    margin: 0;
  }

  dt {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  dd {
    margin: 0;
    font-size: var(--step--1);
    line-height: 1.5;
  }

  .since > summary {
    font-size: var(--step--1);
    color: var(--pencil);
    margin-bottom: 0.75rem;
  }

  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  /* On the right, as a key point's Test me on this is. */
  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.2rem 1rem;
  }

  .link {
    justify-self: start;
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  .link:hover {
    text-decoration: underline;
  }
</style>
