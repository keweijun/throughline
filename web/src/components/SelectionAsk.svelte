<script lang="ts">
  import { enterToSend } from '../lib/keys';
  import { selectionMarkdown } from '../lib/selection';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { stageScroll } from '../lib/stage';
  import { autogrow } from '../lib/autogrow';
  import { highlightAt, occurrenceOf } from '../lib/highlight';
  import type { Annotation, AnnotationSource } from '../lib/types';

  type Pending = { text: string; occurrence: number; turnId: string | null; source?: string; questionId?: string; unit?: string; taskId?: string };

  let visible = $state(false);
  let writing = $state(false);
  let note = $state('');
  let left = $state(0);
  let top = $state(0);
  let pending = $state<Pending | null>(null);
  /** A highlight the learner clicked: the toolbar then edits or removes it instead of offering new ones. */
  let target = $state<Annotation | null>(null);

  // Lessons, side-question answers, exercises and sources can all be highlighted; exercises are not asked about here.
  const annotatable = $derived(!!pending && (!!pending.turnId || !!pending.unit || !!pending.taskId));
  const askable = $derived(!!pending && !pending.taskId);

  // Keep answer selections attached to their existing side question.
  const scope = (node: Node | null | undefined) =>
    (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>('.lesson-body, [data-source-label], [data-question-answer], [data-exercise]') ?? null;

  /** Places the toolbar under a passage, kept inside the window. */
  function place(rect: DOMRect, width: number, height: number) {
    left = Math.max(8, Math.min(rect.left + rect.width / 2 - width / 2, window.innerWidth - width - 8));
    top = Math.max(8, Math.min(rect.bottom + 10, window.innerHeight - height));
  }

  /** The learner's highlight under a click. */
  function clickedHighlight(x: number, y: number): { annotation: Annotation; rect: DOMRect } | null {
    const hit = highlightAt(x, y);
    const annotation = hit && app.state?.annotations.find((a) => a.id === hit.id);
    return annotation ? { annotation, rect: hit.rect } : null;
  }

  function capture(point?: { x: number; y: number; on: EventTarget | null }) {
    if (writing) return;
    visible = false;
    target = null;
    const selection = window.getSelection();
    if (!selection?.rangeCount || !selection.toString().trim()) {
      // A plain click on a highlight offers to note or remove it; links and controls inside keep their own clicks.
      const on = point?.on instanceof Element ? point.on : null;
      const hit = point && !on?.closest('a, button, input, textarea, select, .citation') ? clickedHighlight(point.x, point.y) : null;
      if (!hit) return;
      target = hit.annotation;
      pending = null;
      place(hit.rect, 220, 52);
      visible = true;
      return;
    }
    const area = scope(selection.anchorNode);
    if (!area || area !== scope(selection.focusNode)) return;
    const text = selectionMarkdown(selection, area);
    const anchor = selection.anchorNode instanceof Element ? selection.anchorNode : selection.anchorNode?.parentElement;
    const range = selection.getRangeAt(0);
    // Which repeat of the passage was selected, counted in the element its highlight is painted in (a PDF page's text).
    const occurrence = (passage: string) =>
      area.dataset.sourceLabel
        ? occurrenceOf(anchor?.closest<HTMLElement>('.textLayer') ?? area, passage, range, { loose: true, skip: '.number, .katex, .citation' })
        : occurrenceOf(area, passage, range);
    if (area.dataset.exercise) {
      pending = { text: text.trim(), occurrence: occurrence(text), turnId: null, taskId: area.dataset.exercise };
    } else if (area.dataset.sourceLabel) {
      const passage = text.replace(/\s+/g, ' ').trim();
      pending = { text: passage, occurrence: occurrence(passage), turnId: null, source: area.dataset.sourceLabel, unit: anchor?.closest<HTMLElement>('[data-unit]')?.dataset.unit };
    } else {
      const turnId = area.closest<HTMLElement>('[data-turn-id]')?.dataset.turnId ?? null;
      pending = { text: text.trim(), occurrence: occurrence(text), turnId, questionId: area.closest<HTMLElement>('[data-question-id]')?.dataset.questionId };
    }
    place(range.getBoundingClientRect(), (annotatable ? 180 : 0) + (askable ? 210 : 0), annotatable ? 170 : 52);
    visible = true;
  }

  function ask() {
    if (!pending) return;
    const { text, turnId, source, questionId } = pending;
    app.quote = { text, turnId, source, questionId, scrollY: stageScroll() };
    visible = false;
    window.getSelection()?.removeAllRanges();
    app.openPanel('questions');
    requestAnimationFrame(() => document.getElementById(questionId ? `reply-input-${questionId}` : 'question-input')?.focus());
  }

  function close() {
    visible = false;
    writing = false;
    note = '';
    target = null;
  }

  function startNote() {
    note = target?.note ?? '';
    writing = true;
  }

  async function save(withNote: boolean) {
    if (target) {
      const { id } = target;
      const text = note.trim();
      close();
      await app.editNote(id, text);
      return;
    }
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
      ...(pending.occurrence ? { occurrence: pending.occurrence } : {}),
      ...(text ? { note: text } : {}),
      ...(source ? { source } : pending.taskId ? { task_id: pending.taskId } : { turn_id: pending.turnId }),
    });
  }

  function remove() {
    if (!target) return;
    const { id, note: text } = target;
    if (text && !confirm(t("Delete this note?"))) return;
    close();
    void app.removeAnnotation(id);
  }

  function onNoteKey(event: KeyboardEvent) {
    if (event.key === 'Escape') close();
  }

  let settle: ReturnType<typeof setTimeout> | undefined;

  function onSelectionChange() {
    if (writing || target) return;
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

  function onMouseUp(event: MouseEvent) {
    // Clicks inside the toolbar are its own.
    if (event.target instanceof Element && event.target.closest('.pop')) return;
    const point = { x: event.clientX, y: event.clientY, on: event.target };
    setTimeout(() => capture(point));
  }
</script>

<svelte:document
  onmouseup={onMouseUp}
  ontouchend={() => setTimeout(capture, 50)}
  onkeyup={(e) => (e.key === 'Shift' || e.key.startsWith('Arrow')) && capture()}
  onkeydown={(e) => e.key === 'Escape' && visible && !writing && close()}
  onselectionchange={onSelectionChange}
/>
<svelte:window onscrollcapture={() => !writing && (visible = false)} />

{#if visible && writing}
  <form class="pop writing" style:left="{left}px" style:top="{top}px" onsubmit={(e) => (e.preventDefault(), save(true))}>
    <label for="quick-note">{target?.note ? t("Edit your note") : t("Note on this passage")}</label>
    <!-- svelte-ignore a11y_autofocus -->
    <textarea id="quick-note" rows="3" bind:value={note} use:autogrow={note} use:enterToSend onkeydown={onNoteKey} autofocus placeholder={t("Only you see your notes.")}></textarea>
    <div class="actions">
      <button type="button" class="btn btn-quiet btn-small" onclick={close}>{t("Cancel")}</button>
      <button type="submit" class="btn btn-small" disabled={!target && !note.trim()}>{t("Save note")}</button>
    </div>
  </form>
{:else if visible && target}
  <div class="pop bar" role="toolbar" aria-label={t("Your highlight")} style:left="{left}px" style:top="{top}px">
    <button onpointerdown={(e) => e.preventDefault()} onclick={startNote}>
      <span class="swatch mine" aria-hidden="true"></span>{target.note ? t("Edit note") : t("Add note")}
    </button>
    <button onpointerdown={(e) => e.preventDefault()} onclick={remove}>{t("Remove highlight")}</button>
  </div>
{:else if visible}
  <div class="pop bar" role="toolbar" aria-label={t("Selected passage")} style:left="{left}px" style:top="{top}px">
    {#if annotatable}
      <button onpointerdown={(e) => e.preventDefault()} onclick={() => save(false)}>
        <span class="swatch mine" aria-hidden="true"></span>{t("Highlight")}
      </button>
      <button onpointerdown={(e) => e.preventDefault()} onclick={() => (writing = true)}>{t("Note")}</button>
    {/if}
    {#if askable}
      <button onpointerdown={(e) => e.preventDefault()} onclick={ask}>
        <span class="swatch asked" aria-hidden="true"></span>{t("Ask about this passage")}
      </button>
    {/if}
  </div>
{/if}

<style>
  .pop {
    animation: enter-pop var(--quick) var(--ease-out);
    position: fixed;
    z-index: 50;
    display: flex;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius);
    background: var(--raised);
    box-shadow: var(--shadow);
  }

  .bar {
    padding: 0.2rem;
    gap: 0.1rem;
  }

  .bar > button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.7rem;
    border: 0;
    border-radius: calc(var(--radius) - 2px);
    background: none;
    color: var(--ink);
    font-size: var(--step--1);
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
  }

  .bar > button:hover {
    background: var(--accent-wash);
  }

  .bar > button + button {
    box-shadow: -1px 0 0 var(--rule);
  }

  .swatch {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
  }

  .swatch.mine {
    background: var(--mine-wash);
    box-shadow: inset 0 0 0 1px var(--mine);
  }

  .swatch.asked {
    background: var(--marker-wash);
    box-shadow: inset 0 0 0 1px var(--marker);
  }

  .writing {
    flex-direction: column;
    gap: 0.3rem;
    width: min(340px, calc(100vw - 16px));
    padding: 0.6rem;
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
