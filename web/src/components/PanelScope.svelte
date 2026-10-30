<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { PanelScope } from '../lib/panel';

  // The same three choices, with counts, wherever a side-panel list can be narrowed to part of the course.
  let { scope = $bindable(), counts, label, onchoose }: {
    scope: PanelScope;
    counts: Record<PanelScope, number>;
    label: string;
    onchoose?: () => void;
  } = $props();

  const hasChapter = $derived(!!app.chapterOf(app.viewingId));
  const choices = $derived([
    { value: 'section' as const, label: t("Section") },
    ...(hasChapter ? [{ value: 'chapter' as const, label: t("Chapter") }] : []),
    { value: 'all' as const, label: t("All") },
  ]);
</script>

<div class="segmented panel-scope" role="radiogroup" aria-label={label} onchange={onchoose}>
  {#each choices as choice (choice.value)}
    <label>
      <input type="radio" bind:group={scope} value={choice.value} />
      <span class="name">{choice.label}</span>
      <span class="count">{counts[choice.value]}</span>
    </label>
  {/each}
</div>

<style>
  /* The choices share the width evenly, so they never wrap into a ragged second row. */
  .panel-scope {
    display: grid;
    grid-auto-columns: minmax(0, 1fr);
    grid-auto-flow: column;
    width: 100%;
  }

  label {
    display: flex;
    justify-content: center;
    align-items: baseline;
    gap: 0.35rem;
    min-width: 0;
    padding-inline: 0.5rem;
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .count {
    flex: none;
    font-variant-numeric: tabular-nums;
    opacity: 0.75;
  }
</style>
