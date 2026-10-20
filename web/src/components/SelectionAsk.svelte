<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let visible = $state(false);
  let left = $state(0);
  let top = $state(0);
  let pending: { text: string; turnId: string } | null = null;

  function capture() {
    const selection = window.getSelection();
    if (!selection?.rangeCount || !selection.toString().trim()) return;
    const start = selection.anchorNode?.parentElement;
    const end = selection.focusNode?.parentElement;
    const lesson = start?.closest<HTMLElement>('.lesson-body')?.closest<HTMLElement>('[data-turn-id]');
    if (!lesson || lesson !== end?.closest('.lesson-body')?.closest('[data-turn-id]')) return;
    const formula = start?.closest('.katex');
    // KaTeX holds both MathML and glyphs; a formula-only selection keeps its original TeX.
    const text =
      formula && formula === end?.closest('.katex')
        ? (formula.querySelector('annotation[encoding="application/x-tex"]')?.textContent ?? selection.toString())
        : selection.toString();
    pending = { text: text.trim(), turnId: lesson.dataset.turnId! };
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
    requestAnimationFrame(() => document.getElementById('question-input')?.focus());
  }

  function onSelectionChange() {
    if (!window.getSelection()?.toString().trim()) visible = false;
  }
</script>

<svelte:document
  onmouseup={() => setTimeout(capture)}
  onkeyup={(e) => (e.key === 'Shift' || e.key.startsWith('Arrow')) && capture()}
  onselectionchange={onSelectionChange}
/>
<svelte:window onscroll={() => (visible = false)} />

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
