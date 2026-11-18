<script lang="ts">
  import { t } from '../lib/i18n.svelte';

  /**
   * A confirmation shown next to what asked for it, never as a popup: what will happen, the action and a way back.
   * The action takes the focus, so a learner who pressed Delete with the keyboard confirms with Enter; Escape cancels.
   */
  let {
    message,
    confirmLabel,
    cancelLabel,
    onconfirm,
    oncancel,
    danger = false,
    busy = false,
    compact = false,
  }: {
    message: string;
    confirmLabel: string;
    cancelLabel?: string;
    onconfirm: () => void;
    oncancel: () => void;
    /** The action removes or hides something: its button is drawn in the danger colour. */
    danger?: boolean;
    busy?: boolean;
    /** On one line, for a small row such as a note's or a course card's actions. */
    compact?: boolean;
  } = $props();

  let action = $state<HTMLButtonElement>();
  $effect(() => {
    action?.focus({ preventScroll: true });
  });

  function keydown(event: KeyboardEvent) {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    oncancel();
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div class="inline-confirm" class:compact role="group" aria-label={message} onkeydown={keydown}>
  <p>{message}</p>
  <div class="buttons">
    <button bind:this={action} class="btn btn-small" class:danger disabled={busy} onclick={onconfirm}>{confirmLabel}</button>
    <button class="btn btn-quiet btn-small" disabled={busy} onclick={oncancel}>{cancelLabel ?? t('Cancel')}</button>
  </div>
</div>

<style>
  .inline-confirm {
    animation: enter-rise var(--settle) var(--ease-out);
    display: grid;
    gap: 0.5rem;
    padding: 0.7rem 0.9rem;
    border-radius: var(--radius);
    background: var(--caution-wash);
    color: var(--ink);
    font-size: var(--step--1);
    text-align: left;
  }

  .inline-confirm.compact {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem 0.8rem;
    padding: 0.45rem 0.6rem 0.45rem 0.8rem;
  }

  p {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .danger {
    border-color: var(--danger);
    color: var(--danger);
  }

  .danger:hover {
    background: var(--danger-wash);
    border-color: var(--danger);
  }
</style>
