<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import type { MemoryEntry } from '../lib/types';
  import RememberPrompt from './RememberPrompt.svelte';

  // A preference the teacher suggested takes effect only once the learner confirms it (ADR 0010). It is asked right
  // after the reply or exercise it came from, where the learner is already reading.
  let { entries }: { entries: MemoryEntry[] } = $props();
</script>

{#each entries as entry (entry.id)}
  <div class="suggested-memory" role="group" aria-label={t('Suggested preference')}>
    <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M6 3.5h8v13l-4-3-4 3z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
    <RememberPrompt {entry} />
  </div>
{/each}

<style>
  .suggested-memory {
    animation: enter-rise var(--settle) var(--ease-out);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem 0.6rem;
    margin-top: 1rem;
    padding: 0.55rem 0.6rem 0.55rem 0.8rem;
    border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--rule));
    border-radius: var(--radius);
    background: var(--accent-wash);
    font-size: var(--step-0);
  }

  svg {
    flex: none;
    color: var(--accent);
  }

  .suggested-memory :global(p) {
    flex: 1;
    min-width: 12rem;
    margin: 0;
    color: var(--ink);
  }

  .suggested-memory :global(.btn:not(.btn-quiet)) {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
  }

  .suggested-memory :global(.btn:not(.btn-quiet):hover) {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
  }

  @media (prefers-reduced-motion: reduce) {
    .suggested-memory {
      animation: none;
    }
  }
</style>
