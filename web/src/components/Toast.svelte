<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let toast = $state<HTMLElement>();

  // A manual popover floats in the top layer, so the confirmation overlays the page without moving it and
  // still shows above the Settings dialog, where an update link can raise it.
  $effect(() => {
    if (!toast) return;
    if (app.notice) {
      // Reopening puts it back above anything shown since, such as a dialog opened after the first notice.
      if (toast.matches(':popover-open')) toast.hidePopover();
      toast.showPopover();
    } else if (toast.matches(':popover-open')) toast.hidePopover();
  });
</script>

<div class="toast" popover="manual" role="status" bind:this={toast}>
  {#if app.notice}
    <span class="mark" aria-hidden="true">
      <svg viewBox="0 0 20 20" width="12" height="12"><path d="M4.5 10.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </span>
    <div class="text">
      <p class="title">{app.notice.title}</p>
      {#if app.notice.detail}<p class="detail">{app.notice.detail}</p>{/if}
    </div>
    <button class="close" onclick={() => (app.notice = null)} aria-label={t('Dismiss')}>
      <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
    </button>
  {/if}
</div>

<style>
  .toast {
    position: fixed;
    inset: auto 0 1.5rem;
    margin: 0 auto;
    display: none;
    align-items: flex-start;
    gap: 0.7rem;
    width: max-content;
    max-width: min(26rem, calc(100vw - 2rem));
    padding: 0.7rem 0.6rem 0.7rem 0.85rem;
    background: var(--raised);
    color: var(--ink);
    border: 1px solid var(--rule);
    border-radius: calc(var(--radius) + 2px);
    box-shadow: var(--shadow);
    font-size: var(--step-0);
  }

  .toast:popover-open {
    display: flex;
    animation: enter-rise var(--settle) var(--ease-out);
  }

  .mark {
    flex: none;
    display: grid;
    place-items: center;
    width: 1.25rem;
    height: 1.25rem;
    margin-top: 0.05rem;
    border-radius: 50%;
    background: var(--good-wash);
    color: var(--good);
  }

  .text {
    min-width: 0;
  }

  .text p {
    margin: 0;
    line-height: 1.4;
  }

  .title {
    font-weight: 600;
  }

  .detail {
    margin-top: 0.15rem;
    color: var(--pencil);
    font-size: var(--step--1);
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

  @media (prefers-reduced-motion: reduce) {
    .toast:popover-open {
      animation: none;
    }
  }
</style>
