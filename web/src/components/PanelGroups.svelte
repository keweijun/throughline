<script lang="ts" generics="T">
  import type { Snippet } from 'svelte';
  import { slide } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import type { PanelGroup, PanelScope } from '../lib/panel';

  // One way to list side-panel items under their chapter and section; a single section needs no heading of its own.
  let { groups, scope, key, item, empty }: {
    groups: PanelGroup<T>[];
    scope: PanelScope;
    key: (item: T) => string;
    item: Snippet<[T]>;
    empty: string;
  } = $props();
</script>

{#each groups as group, i (group.key)}
  {#if scope === 'all' && group.chapter && group.chapter.id !== groups[i - 1]?.chapter?.id}
    <h3 class="chapter">{group.chapter.title}</h3>
  {/if}
  <section class="group" aria-label={group.title}>
    {#if scope !== 'section'}<h3 class="section">{group.title}</h3>{/if}
    <div class="items">
      {#each group.items as entry (key(entry))}
        <div transition:slide={{ duration: prefersReducedMotion.current ? 0 : 200 }}>{@render item(entry)}</div>
      {/each}
    </div>
  </section>
{:else}
  <p class="panel-empty">{empty}</p>
{/each}

<style>
  .chapter {
    margin-top: 0.6rem;
    font-size: var(--step-0);
    font-weight: 600;
    color: var(--ink);
  }

  .chapter:first-child {
    margin-top: 0;
  }

  .section {
    margin-bottom: 0.5rem;
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--pencil);
  }

  .items {
    display: grid;
    gap: 0.75rem;
  }
</style>
