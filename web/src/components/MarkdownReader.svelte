<script lang="ts">
  import { onMount } from 'svelte';
  import { mark, clear } from '../lib/highlight';

  let {
    lines,
    target,
    label,
    highlights = [],
  }: { lines: { id: string; text: string }[]; target: string; label: string; highlights?: string[] } = $props();

  let container: HTMLElement | undefined = $state();

  onMount(() => {
    container?.querySelector('.cited')?.scrollIntoView({ block: 'center' });
  });

  $effect(() => {
    if (!container) return;
    mark('mine', 'markdown-reader', container, highlights, { loose: true, skip: '.number' });
    return () => clear('mine', 'markdown-reader');
  });
</script>

<div class="doc" bind:this={container} data-source-label={label}>
  {#each lines as line, i (line.id)}
    <div class="line" class:cited={line.id === target} class:blank={!line.text.trim()} data-unit={line.id}>
      <span class="number" aria-hidden="true">{i + 1}</span>
      <span class="text">{line.text || ' '}</span>
    </div>
  {/each}
</div>

<style>
  .doc {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: 0.75rem 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    background: var(--raised);
    font-family: var(--serif);
    font-size: var(--step-0);
    line-height: 1.65;
  }

  .line {
    display: grid;
    grid-template-columns: 2.6rem minmax(0, 1fr);
    padding-right: 1rem;
  }

  .number {
    padding-right: 0.8rem;
    text-align: right;
    font-family: var(--sans);
    font-size: var(--step--1);
    color: var(--pencil);
    opacity: 0.7;
    user-select: none;
    font-variant-numeric: tabular-nums;
  }

  .text {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .cited {
    background: var(--marker-wash);
    box-shadow: inset 3px 0 var(--marker);
  }

  .cited .number {
    color: var(--ink);
    opacity: 1;
    font-weight: 600;
  }
</style>
