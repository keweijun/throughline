<script lang="ts">
  import { t, diagnostic } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import RememberPrompt from './RememberPrompt.svelte';

  // Messages float over the page rather than pushing it down. An error and a suggested preference need the learner,
  // so they sit at the top and stay until answered; a confirmation is safe to ignore, sits at the bottom and clears
  // itself.
  const suggestion = $derived(
    app.libraryOpen || (app.panelOpen && app.panelTab === 'memory') ? undefined : app.state?.memory?.find((e) => e.status === 'suggested'),
  );

  let top = $state<HTMLElement>();
  let bottom = $state<HTMLElement>();

  // A manual popover sits in the top layer, so a stack also shows above the Settings dialog. Reopening it when a
  // new message arrives puts it back above anything shown since, such as a dialog opened after the last message.
  function float(stack: () => HTMLElement | undefined, current: () => unknown[]) {
    let shown: unknown[] = [];
    $effect(() => {
      const element = stack();
      if (!element) return;
      const messages = current();
      const arrived = messages.some((message, i) => message && message !== shown[i]);
      shown = messages;
      const open = element.matches(':popover-open');
      if (!messages.some(Boolean)) {
        if (open) element.hidePopover();
      } else if (arrived) {
        if (open) element.hidePopover();
        element.showPopover();
      }
    });
  }
  float(() => top, () => [app.error, suggestion?.id]);
  float(() => bottom, () => [app.notice]);

  const close = '<path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />';
</script>

<div class="toasts top" popover="manual" bind:this={top}>
  {#if app.error}
    <div class="toast error" role="alert">
      <span class="mark" aria-hidden="true">
        <svg viewBox="0 0 20 20" width="12" height="12"><path d="M10 5v6M10 14.5v.5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" /></svg>
      </span>
      <p class="text">{diagnostic(app.error)}</p>
      <button class="close" onclick={() => (app.error = null)} aria-label={t('Dismiss')}>
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">{@html close}</svg>
      </button>
    </div>
  {/if}

  <!-- A preference the teacher suggested takes effect only once the learner confirms it (ADR 0010). -->
  {#if suggestion}
    <div class="toast suggestion" role="status">
      <span class="mark" aria-hidden="true">
        <svg viewBox="0 0 20 20" width="12" height="12"><path d="M6 3.5h8v13l-4-3-4 3z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /></svg>
      </span>
      <div class="text"><RememberPrompt entry={suggestion} /></div>
    </div>
  {/if}
</div>

<div class="toasts bottom" popover="manual" bind:this={bottom}>
  {#if app.notice}
    <div class="toast" role="status">
      <span class="mark" aria-hidden="true">
        <svg viewBox="0 0 20 20" width="12" height="12"><path d="M4.5 10.5l3.5 3.5 7.5-8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </span>
      <div class="text">
        <p class="title">{app.notice.title}</p>
        {#if app.notice.detail}<p class="detail">{app.notice.detail}</p>{/if}
      </div>
      <button class="close" onclick={() => (app.notice = null)} aria-label={t('Dismiss')}>
        <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">{@html close}</svg>
      </button>
    </div>
  {/if}
</div>

<style>
  /* The stack itself is invisible and lets clicks through; only its cards take them. */
  .toasts {
    position: fixed;
    inset-inline: 0;
    margin: 0 auto;
    display: none;
    flex-direction: column;
    gap: 0.5rem;
    width: fit-content;
    max-width: min(28rem, calc(100vw - 2rem));
    padding: 0;
    overflow: visible;
    background: none;
    border: 0;
    pointer-events: none;
  }

  .toasts:popover-open {
    display: flex;
  }

  /* Just below the top bar, where the learner looks first. */
  .top {
    inset-block: calc(var(--topbar) + 0.75rem) auto;
  }

  .bottom {
    inset-block: auto 1.5rem;
  }

  .toast {
    pointer-events: auto;
    display: flex;
    align-items: flex-start;
    gap: 0.7rem;
    animation: enter-drop var(--settle) var(--ease-out);
    padding: 0.7rem 0.6rem 0.7rem 0.85rem;
    background: var(--raised);
    color: var(--ink);
    border: 1px solid var(--rule);
    border-radius: calc(var(--radius) + 2px);
    box-shadow: var(--shadow);
    font-size: var(--step-0);
  }

  @media (prefers-reduced-motion: reduce) {
    .toast {
      animation: none;
    }
  }

  .toast.error {
    border-color: color-mix(in srgb, var(--danger) 35%, var(--rule));
  }

  .bottom .toast {
    animation-name: enter-rise;
  }

  /* The suggestion waits on the learner's answer, so it carries the accent. */
  .toast.suggestion {
    padding-right: 0.85rem;
    background: color-mix(in srgb, var(--accent-wash) 55%, var(--raised));
    border-color: color-mix(in srgb, var(--accent) 45%, var(--rule));
  }

  .suggestion .text :global(.btn:not(.btn-quiet)) {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
  }

  .suggestion .text :global(.btn:not(.btn-quiet):hover) {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
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

  .error .mark {
    background: var(--danger-wash);
    color: var(--danger);
  }

  .suggestion .mark {
    background: var(--accent-wash);
    color: var(--accent);
  }

  .text {
    flex: 1;
    min-width: 0;
    margin: 0;
    line-height: 1.4;
    overflow-wrap: anywhere;
  }

  .text p,
  .text :global(p) {
    margin: 0;
  }

  .suggestion .text :global(.remember-actions) {
    margin-top: 0.45rem;
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
</style>
