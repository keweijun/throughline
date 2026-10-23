<script lang="ts">
  import { selectionMarkdown } from '../lib/selection';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let visible = $state(false);
  let left = $state(0);
  let top = $state(0);
  let pending: { text: string; turnId: string | null; source?: string; questionId?: string } | null = null;

  // Keep answer selections attached to their existing side question.
  const scope = (node: Node | null | undefined) =>
    (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>('.lesson-body, [data-source-label], [data-question-answer]') ?? null;

  function capture() {
    visible = false;
    const selection = window.getSelection();
    if (!selection?.rangeCount || !selection.toString().trim()) return;
    const area = scope(selection.anchorNode);
    if (!area || area !== scope(selection.focusNode)) return;
    const text = selectionMarkdown(selection, area);
    pending = area.dataset.sourceLabel
      ? { text: text.replace(/\s+/g, ' ').trim(), turnId: null, source: area.dataset.sourceLabel }
      : { text: text.trim(), turnId: area.closest<HTMLElement>('[data-turn-id]')?.dataset.turnId ?? null, questionId: area.closest<HTMLElement>('[data-question-id]')?.dataset.questionId };
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    left = Math.max(8, Math.min(rect.left + rect.width / 2 - 95, window.innerWidth - 198));
    top = Math.max(8, Math.min(rect.bottom + 10, window.innerHeight - 52));
    visible = true;
  }

  function ask() {
    if (!pending) return;
    app.quote = { ...pending, scrollY: window.scrollY };
    visible = false;
    window.getSelection()?.removeAllRanges();
    app.openPanel('questions');
    requestAnimationFrame(() => document.getElementById(pending?.questionId ? `reply-input-${pending.questionId}` : 'question-input')?.focus());
  }

  let settle: ReturnType<typeof setTimeout> | undefined;

  function onSelectionChange() {
    if (!window.getSelection()?.toString().trim()) {
      visible = false;
      return;
    }
    // Touch selections arrive through handle drags rather than mouseup, so offer the button once the selection settles.
    if (matchMedia('(pointer: coarse)').matches) {
      clearTimeout(settle);
      settle = setTimeout(capture, 450);
    }
  }
</script>

<svelte:document
  onmouseup={() => setTimeout(capture)}
  ontouchend={() => setTimeout(capture, 50)}
  onkeyup={(e) => (e.key === 'Shift' || e.key.startsWith('Arrow')) && capture()}
  onselectionchange={onSelectionChange}
/>
<svelte:window onscrollcapture={() => (visible = false)} />

{#if visible}
  <button
    class="ask"
    style:left="{left}px"
    style:top="{top}px"
    onpointerdown={(e) => e.preventDefault()}
    onclick={ask}
  >
    {t("Ask about this passage")}
  </button>
{/if}

<style>
  .ask {
    position: fixed;
    z-index: 50;
    padding: 0.45rem 0.8rem;
    border: 1px solid #c9a82b;
    border-radius: var(--radius);
    background: var(--marker);
    color: #2a2208;
    font-size: var(--step--1);
    font-weight: 600;
    box-shadow: var(--shadow);
    cursor: pointer;
  }

  .ask:hover {
    filter: brightness(1.04);
  }
</style>
