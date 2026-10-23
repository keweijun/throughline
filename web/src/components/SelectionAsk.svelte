<script lang="ts">
  import { selectionMarkdown } from '../lib/selection';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { AnnotationSource } from '../lib/types';

  type Pending = { text: string; turnId: string | null; source?: string; questionId?: string; unit?: string; taskId?: string };

  let visible = $state(false);
  let writing = $state(false);
  let note = $state('');
  let left = $state(0);
  let top = $state(0);
  let pending = $state<Pending | null>(null);

  // Lessons, side-question answers, exercises and sources can all be highlighted; exercises are not asked about here.
  const annotatable = $derived(!!pending && (!!pending.turnId || !!pending.unit || !!pending.taskId));
  const askable = $derived(!!pending && !pending.taskId);

  // Keep answer selections attached to their existing side question.
  const scope = (node: Node | null | undefined) =>
    (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>('.lesson-body, [data-source-label], [data-question-answer], [data-exercise]') ?? null;

  function capture() {
    if (writing) return;
    visible = false;
    const selection = window.getSelection();
    if (!selection?.rangeCount || !selection.toString().trim()) return;
    const area = scope(selection.anchorNode);
    if (!area || area !== scope(selection.focusNode)) return;
    const text = selectionMarkdown(selection, area);
    const anchor = selection.anchorNode instanceof Element ? selection.anchorNode : selection.anchorNode?.parentElement;
    pending = area.dataset.exercise
      ? { text: text.trim(), turnId: null, taskId: area.dataset.exercise }
      : area.dataset.sourceLabel
      ? { text: text.replace(/\s+/g, ' ').trim(), turnId: null, source: area.dataset.sourceLabel, unit: anchor?.closest<HTMLElement>('[data-unit]')?.dataset.unit }
      : { text: text.trim(), turnId: area.closest<HTMLElement>('[data-turn-id]')?.dataset.turnId ?? null, questionId: area.closest<HTMLElement>('[data-question-id]')?.dataset.questionId };
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    const width = (annotatable ? 160 : 0) + (askable ? 198 : 0);
    left = Math.max(8, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width));
    top = Math.max(8, Math.min(rect.bottom + 10, window.innerHeight - (annotatable ? 170 : 52)));
    visible = true;
  }

  function ask() {
    if (!pending) return;
    const { text, turnId, source, questionId } = pending;
    app.quote = { text, turnId, source, questionId, scrollY: window.scrollY };
    visible = false;
    window.getSelection()?.removeAllRanges();
    app.openPanel('questions');
    requestAnimationFrame(() => document.getElementById(questionId ? `reply-input-${questionId}` : 'question-input')?.focus());
  }

  function close() {
    visible = false;
    writing = false;
    note = '';
  }

  async function save(withNote: boolean) {
    if (!pending) return;
    const source: AnnotationSource | undefined =
      pending.unit && app.source
        ? {
            source_id: app.source.source_id,
            revision: app.source.revision,
            unit_id: pending.unit,
            label: pending.source,
            ...(pending.unit.startsWith('page-') ? { page: Number(pending.unit.slice(5)) } : {}),
          }
        : undefined;
    // The host takes the section from the lesson, answer or exercise; a source passage belongs to the section being read.
    const conceptId = (pending.turnId && app.turn(pending.turnId)?.concept_id) || app.viewingId;
    if (!conceptId) return;
    const text = withNote ? note.trim() : '';
    close();
    window.getSelection()?.removeAllRanges();
    await app.annotate({
      kind: 'highlight',
      concept_id: conceptId,
      passage: pending.text,
      ...(text ? { note: text } : {}),
      ...(source ? { source } : pending.taskId ? { task_id: pending.taskId } : { turn_id: pending.turnId }),
    });
  }

  function onNoteKey(event: KeyboardEvent) {
    if (event.key === 'Escape') close();
    if (event.key === 'Enter' && !event.shiftKey && note.trim()) {
      event.preventDefault();
      void save(true);
    }
  }

  let settle: ReturnType<typeof setTimeout> | undefined;

  function onSelectionChange() {
    if (writing) return;
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
<svelte:window onscrollcapture={() => !writing && (visible = false)} />

{#if visible && writing}
  <form class="pop writing" style:left="{left}px" style:top="{top}px" onsubmit={(e) => (e.preventDefault(), save(true))}>
    <label for="quick-note">{t("Note on this passage")}</label>
    <!-- svelte-ignore a11y_autofocus -->
    <textarea id="quick-note" rows="3" bind:value={note} onkeydown={onNoteKey} autofocus placeholder={t("Only you see your notes.")}></textarea>
    <div class="actions">
      <button type="button" class="btn btn-quiet btn-small" onclick={close}>{t("Cancel")}</button>
      <button type="submit" class="btn btn-small" disabled={!note.trim()}>{t("Save note")}</button>
    </div>
  </form>
{:else if visible}
  <div class="pop" role="toolbar" aria-label={t("Selected passage")} style:left="{left}px" style:top="{top}px">
    {#if annotatable}
      <button class="mine" onpointerdown={(e) => e.preventDefault()} onclick={() => save(false)}>{t("Highlight")}</button>
      <button class="mine" onpointerdown={(e) => e.preventDefault()} onclick={() => (writing = true)}>{t("Note")}</button>
    {/if}
    {#if askable}
      <button class="ask" onpointerdown={(e) => e.preventDefault()} onclick={ask}>{t("Ask about this passage")}</button>
    {/if}
  </div>
{/if}

<style>
  .pop {
    animation: enter-pop var(--quick) var(--ease-out);
    position: fixed;
    z-index: 50;
    display: flex;
    gap: 0.3rem;
  }

  .pop > button {
    padding: 0.45rem 0.8rem;
    border-radius: var(--radius);
    font-size: var(--step--1);
    font-weight: 600;
    box-shadow: var(--shadow);
    cursor: pointer;
  }

  .ask {
    border: 1px solid #c9a82b;
    background: var(--marker);
    color: #2a2208;
  }

  .mine {
    border: 1px solid var(--mine);
    background: var(--raised);
    color: var(--ink);
  }

  .pop > button:hover {
    filter: brightness(1.04);
  }

  .writing {
    flex-direction: column;
    width: min(340px, calc(100vw - 16px));
    padding: 0.6rem;
    border: 1px solid var(--mine);
    border-radius: var(--radius);
    background: var(--raised);
    box-shadow: var(--shadow);
  }

  .writing label {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .writing textarea {
    width: 100%;
    resize: vertical;
    font-size: var(--step-0);
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.3rem;
  }
</style>
