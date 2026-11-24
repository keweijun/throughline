<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { reviewable as studied, type ReviewScope } from '../lib/scope.svelte';

  /** Narrows the Review place to chapters or sections; with none chosen it covers everything studied. */
  let { value, onchange }: { value: ReviewScope; onchange: (value: ReviewScope) => void } = $props();

  const chapters = $derived(app.chapters.filter((c) => c.concept_ids.some(studied)));
  // A course without chapters is one chapter named after the course: Everything studied already covers it.
  const chips = $derived(app.wholeCourse ? [] : chapters);
  const everything = $derived(!value.chapter_ids.length && !value.concept_ids.length);
  let choosing = $state(false);

  function chapter(id: string) {
    const ids = value.chapter_ids.includes(id) ? value.chapter_ids.filter((x) => x !== id) : [...value.chapter_ids, id];
    // A chapter chosen whole covers its sections; drop them as separate choices.
    const sections = app.chapters.find((c) => c.id === id)?.concept_ids ?? [];
    onchange({ chapter_ids: ids, concept_ids: value.concept_ids.filter((x) => !sections.includes(x)) });
  }

  function section(id: string) {
    onchange({ ...value, concept_ids: value.concept_ids.includes(id) ? value.concept_ids.filter((x) => x !== id) : [...value.concept_ids, id] });
  }
</script>

<div class="scope" role="group" aria-label={t("What to review")}>
  <button class="chip-toggle" aria-pressed={everything} onclick={() => onchange({ chapter_ids: [], concept_ids: [] })}>{t("Everything studied")}</button>
  {#each chips as item (item.id)}
    <button class="chip-toggle" aria-pressed={value.chapter_ids.includes(item.id)} onclick={() => chapter(item.id)}>{item.title}</button>
  {/each}
  <button class="chip-toggle choose" aria-expanded={choosing} onclick={() => (choosing = !choosing)}>{t("Choose sections")} <span aria-hidden="true">{choosing ? '▴' : '▾'}</span></button>
</div>
{#if choosing}
  <div class="sections">
    {#each chapters as item (item.id)}
      <fieldset>
        {#if !app.wholeCourse}<legend>{item.title}</legend>{/if}
        {#each item.concept_ids.filter(studied) as id (id)}
          <label>
            <input type="checkbox" checked={value.chapter_ids.includes(item.id) || value.concept_ids.includes(id)} disabled={value.chapter_ids.includes(item.id)} onchange={() => section(id)} />
            {app.concept(id)?.title ?? id}
          </label>
        {/each}
      </fieldset>
    {/each}
  </div>
{/if}

<style>
  .scope {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
  }

  .chip-toggle {
    padding: 0.2rem 0.7rem;
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--ink-soft);
    font-size: var(--step--1);
    cursor: pointer;
  }

  .choose {
    border-style: dashed;
  }

  .chip-toggle[aria-pressed='true'],
  .choose[aria-expanded='true'] {
    border-color: var(--accent);
    background: var(--accent-wash);
    color: var(--accent);
  }

  .sections {
    display: grid;
    gap: 0.75rem;
    margin-top: 0.75rem;
    padding: 0.85rem 1.1rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
  }

  fieldset {
    display: grid;
    gap: 0.3rem;
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    margin-bottom: 0.2rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--step-0);
  }
</style>
