<script lang="ts">
  import type { Snippet } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  // A one-time hint (ADR 0017) for a gesture nothing on screen reveals. It sits next to what it explains, shows the
  // first time that thing appears, one hint at a time, and is gone for good once dismissed or acted on.
  let { id, children }: { id: string; children: Snippet } = $props();

  const key = $derived(`hint-${id}`);
  // Every copy of a hint (one per lesson step, say) competes for one slot, so it appears once on the page.
  const me = {};
  const unseen = $derived(!!app.seen && !app.seen.includes(key));

  $effect(() => {
    if (unseen && !app.hint) app.hint = { key, owner: me };
  });

  $effect(() => () => {
    if (app.hint?.owner === me) app.hint = null;
  });

  const showing = $derived(unseen && app.hint?.owner === me);
</script>

{#if showing}
  <aside class="hint" aria-label={t('Tip')}>
    <span class="label">{t('Tip')}</span>
    <p>{@render children()}</p>
    <button class="btn btn-quiet btn-small" onclick={() => app.markSeen(key)}>{t('Got it')}</button>
  </aside>
{/if}

<style>
  .hint {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: baseline;
    gap: 0.6rem;
    margin: 0.9rem 0;
    padding: 0.55rem 0.75rem;
    border-left: 3px solid var(--marker);
    border-radius: 0 var(--radius) var(--radius) 0;
    background: var(--marker-wash);
    font-size: var(--step--1);
    animation: enter-drop var(--settle) var(--ease-out);
  }

  .label {
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    font-size: 0.7rem;
    color: var(--ink-soft);
  }

  p {
    margin: 0;
    line-height: 1.45;
  }
</style>
