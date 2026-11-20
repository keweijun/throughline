<script lang="ts">
  import { locale, t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { markdown } from '../lib/markdown';
  import type { KeyPoint, SectionKeyPoints } from '../lib/types';
  import CodexLink from './CodexLink.svelte';

  /**
   * A section's key points (ADR 0024): each with when it holds, the mistake to avoid and links back to the lesson and
   * pages that taught it. The learner cannot edit them; changing them is a request to Codex. With `section`, the list is
   * one section of a chapter sheet and names it instead of carrying a heading of its own.
   */
  let { value, section = false }: { value: SectionKeyPoints; section?: boolean } = $props();

  const concept = $derived(app.concept(value.concept_id));
  const course = $derived(app.libraryCourse);
  const md = (text: string, point?: KeyPoint) => ({ language: locale.language, text, refs: point?.source_refs ?? [], onSource: (r: KeyPoint['source_refs'][number]) => app.openSource(r) });
  // The citations a point links, written as the lesson writes them, so they peek and open like the lesson's own.
  const cited = (point: KeyPoint) => point.source_refs.map((r) => `[Source ${r.source_id} / ${r.unit_id}]`).join(' ');

  function taughtIn(point: KeyPoint) {
    if (!point.turn_id || !app.turn(point.turn_id)) return null;
    const step = app.stepOf(point.turn_id);
    return step ? t('Step {number}', { number: step.number }) : t('Lesson');
  }
</script>

<section class="key-points" class:in-sheet={section} aria-label={section ? concept?.title : t("Key points")}>
  {#if section}
    <h3><button class="link" onclick={() => app.view(value.concept_id)}>{concept?.title ?? value.concept_id}</button></h3>
  {:else}
    <header>
      <h2>{t("Key points")}</h2>
      {#if course && concept}
        <CodexLink
          class="change"
          prompt={t('$throughline change the key points of the section "{section}" in the course {course}: ', { section: concept.title, course: course.name })}
          origin={{ label: t('Key points: {section}', { section: concept.title }), text: `key points of section "${concept.title}" (${concept.id})` }}
        >{t("Ask Codex to change them")}</CodexLink>
      {/if}
    </header>
  {/if}
  <ol>
    {#each value.points as point, index (index)}
      {@const where = taughtIn(point)}
      <li>
        <div class="prose statement" use:markdown={md(point.statement, point)}></div>
        {#if point.holds_when || point.common_mistake}
          <dl>
            {#if point.holds_when}
              <div><dt>{t("Holds when")}</dt><dd class="prose" use:markdown={md(point.holds_when, point)}></dd></div>
            {/if}
            {#if point.common_mistake}
              <div class="mistake"><dt>{t("Common mistake")}</dt><dd class="prose" use:markdown={md(point.common_mistake, point)}></dd></div>
            {/if}
          </dl>
        {/if}
        {#if where || point.source_refs.length}
          <p class="taught">
            {#if where}<button class="link" onclick={() => app.showLesson(point.turn_id!)}>{where}</button>{/if}
            {#if point.source_refs.length}<span class="cited" use:markdown={md(cited(point), point)}></span>{/if}
          </p>
        {/if}
      </li>
    {/each}
  </ol>
</section>

<style>
  .key-points {
    display: grid;
    gap: 0.75rem;
    padding: 1.1rem 1.3rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
  }

  .key-points.in-sheet {
    padding: 0;
    border: 0;
    background: none;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.4rem 1rem;
  }

  h2 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  h3 {
    font-size: var(--step-0);
    font-weight: 600;
  }

  header :global(.change) {
    font-size: var(--step--1);
  }

  ol {
    display: grid;
    gap: 1rem;
    margin: 0;
    padding-left: 1.4rem;
  }

  li::marker {
    color: var(--pencil);
    font-variant-numeric: tabular-nums;
  }

  .statement {
    font-size: var(--step-0);
    line-height: 1.55;
  }

  /* One label column for the point, as wide as its longest label. */
  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.25rem 1rem;
    align-items: baseline;
    margin: 0.4rem 0 0;
  }

  dl > div {
    display: contents;
  }

  dt {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .mistake dt {
    color: var(--accent);
  }

  dd {
    margin: 0;
    font-size: var(--step--1);
    line-height: 1.5;
    color: var(--ink-soft);
  }

  .taught {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.2rem 0.75rem;
    margin-top: 0.35rem;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .cited :global(p) {
    display: inline;
  }

  .link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--accent);
    font: inherit;
    cursor: pointer;
  }

  .link:hover {
    text-decoration: underline;
  }
</style>
