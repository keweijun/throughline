<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let toast = $state<HTMLElement>();
  let shown: string | null = null;

  // An error floats just below the top bar rather than pushing the page down, and stays until dismissed. A manual
  // popover sits in the top layer, so it also shows above the Settings dialog; reopening it when a new error arrives
  // puts it back above anything shown since, such as a dialog opened after the last error.
  $effect(() => {
    if (!toast) return;
    const error = app.error;
    const open = toast.matches(':popover-open');
    if (!error) {
      if (open) toast.hidePopover();
    } else if (error !== shown) {
      if (open) toast.hidePopover();
      toast.showPopover();
    }
    shown = error;
  });
</script>

<div class="toast" popover="manual" role="alert" bind:this={toast}>
  {#if app.error}
    <span class="mark" aria-hidden="true">
      <svg viewBox="0 0 20 20" width="12" height="12"><path d="M10 5v6M10 14.5v.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" /></svg>
    </span>
    <p class="text">{diagnostic(app.error)}</p>
    <button class="close" onclick={() => (app.error = null)} aria-label={t('Dismiss')}>
      <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
    </button>
  {/if}
</div>

<style>
  .toast {
    position: fixed;
    inset: calc(var(--topbar) + 0.75rem) 0 auto;
    margin: 0 auto;
    display: none;
    align-items: flex-start;
    gap: 0.7rem;
    width: fit-content;
    max-width: min(28rem, calc(100vw - 2rem));
    padding: 0.7rem 0.6rem 0.7rem 0.85rem;
    background: var(--raised);
    color: var(--ink);
    border: 1px solid color-mix(in srgb, var(--danger) 35%, var(--rule));
    border-radius: calc(var(--radius) + 2px);
    box-shadow: var(--shadow);
    font-size: var(--step-0);
  }

  .toast:popover-open {
    display: flex;
    animation: enter-drop var(--settle) var(--ease-out);
  }

  @media (prefers-reduced-motion: reduce) {
    .toast:popover-open {
      animation: none;
    }
  }

  .mark {
    flex: none;
    display: grid;
    place-items: center;
    width: 1.25rem;
    height: 1.25rem;
    margin-top: 0.05rem;
    border-radius: 50%;
    background: var(--danger-wash);
    color: var(--danger);
  }

  .text {
    flex: 1;
    min-width: 0;
    margin: 0;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  .close {
    flex: none;
    display: grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    margin: -0.2rem 0 0 0.2rem;
    padding: 0;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--pencil);
    cursor: pointer;
  }

  .close:hover {
    background: var(--ground);
    color: var(--ink);
  }
</style>
