<script lang="ts">
  import { selectionMarkdown } from '../lib/selection';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { stageScroll } from '../lib/stage';
  import { highlightAt, occurrenceOf } from '../lib/highlight';
  import type { NoteQuote } from '../lib/store.svelte';
  import type { Annotation, AnnotationSource } from '../lib/types';

  type Pending = {
    text: string;
    occurrence: number;
    turnId: string | null;
    source?: string;
    questionId?: string;
    unit?: string;
    taskId?: string;
    /** The section the passage belongs to when it is not the page's, such as an exercise's on a chapter or review page. */
    conceptId?: string;
    /** A check question's passage can be asked about but not highlighted. */
    check?: boolean;
  };

  let visible = $state(false);
  let left = $state(0);
  let top = $state(0);
  /** The passage the toolbar points at, and which side of it the toolbar sits on. */
  let anchor = $state<DOMRect | null>(null);
  let side = $state<'above' | 'below'>('above');
  let caret = $state(0);
  let pop: HTMLElement | undefined = $state();
  let pending = $state<Pending | null>(null);
  /** A highlight the learner clicked: the toolbar then edits or removes it instead of offering new ones. */
  let target = $state<Annotation | null>(null);

  // Lessons, side-question answers, exercises and sources can all be highlighted, and anything selected can be asked about.
  const annotatable = $derived(!!pending && !pending.check && (!!pending.turnId || !!pending.unit || !!pending.taskId));

  // Keep answer selections attached to their existing side question.
  const scope = (node: Node | null | undefined) =>
    (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>('.lesson-body, [data-source-label], [data-question-answer], [data-exercise], [data-check]') ?? null;

  function place(rect: DOMRect) {
    anchor = rect;
  }

  // Once shown, centre on the passage at its real size, above it so the next lines stay readable, or below it when the
  // window edge is too close.
  $effect(() => {
    if (!pop || !anchor) return;
    const { width, height } = pop.getBoundingClientRect();
    const gap = 10;
    // The top bar covers the top of the window, so the reading area's top is the edge to keep clear of.
    const edge = (document.getElementById('stage')?.getBoundingClientRect().top ?? 0) + 8;
    const fitsAbove = anchor.top - gap - height >= edge;
    const fitsBelow = anchor.bottom + gap + height <= window.innerHeight - 8;
    side = fitsAbove || !fitsBelow ? 'above' : 'below';
    top = side === 'above' ? Math.max(edge, anchor.top - gap - height) : Math.min(anchor.bottom + gap, window.innerHeight - height - 8);
    const centre = anchor.left + anchor.width / 2;
    left = Math.max(8, Math.min(centre - width / 2, window.innerWidth - width - 8));
    caret = Math.max(12, Math.min(centre - left, width - 12));
  });

  /** The learner's highlight under a click. */
  function clickedHighlight(x: number, y: number): { annotation: Annotation; rect: DOMRect } | null {
    const hit = highlightAt(x, y);
    const annotation = hit && app.state?.annotations.find((a) => a.id === hit.id);
    return annotation ? { annotation, rect: hit.rect } : null;
  }

  function capture(point?: { x: number; y: number; on: EventTarget | null }) {
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
      place(hit.rect);
      visible = true;
      return;
    }
    const area = scope(selection.anchorNode);
    if (!area || area !== scope(selection.focusNode)) return;
    const text = selectionMarkdown(selection, area);
    if (!text) return;
    const anchor = selection.anchorNode instanceof Element ? selection.anchorNode : selection.anchorNode?.parentElement;
    const range = selection.getRangeAt(0);
    // Which repeat of the passage was selected, counted in the element its highlight is painted in (a PDF page's text).
    const occurrence = (passage: string) =>
      area.dataset.sourceLabel
        ? occurrenceOf(anchor?.closest<HTMLElement>('.textLayer') ?? area, passage, range, { loose: true, skip: '.number, .katex, .citation, .widget' })
        : occurrenceOf(area, passage, range);
    if (area.dataset.check !== undefined) {
      // A lesson's check question asks about that lesson; a review's recall question about the question itself.
      const turnId = area.dataset.task ? null : (area.closest<HTMLElement>('[data-turn-id]')?.dataset.turnId ?? null);
      pending = { text: text.trim(), occurrence: 0, turnId, taskId: area.dataset.task, conceptId: area.dataset.section, check: true };
    } else if (area.dataset.exercise) {
      pending = { text: text.trim(), occurrence: occurrence(text), turnId: null, taskId: area.dataset.exercise, conceptId: area.dataset.section };
    } else if (area.dataset.sourceLabel) {
      const passage = text.replace(/\s+/g, ' ').trim();
      pending = { text: passage, occurrence: occurrence(passage), turnId: null, source: area.dataset.sourceLabel, unit: anchor?.closest<HTMLElement>('[data-unit]')?.dataset.unit };
    } else {
      const turnId = area.closest<HTMLElement>('[data-turn-id]')?.dataset.turnId ?? null;
      pending = { text: text.trim(), occurrence: occurrence(text), turnId, questionId: area.closest<HTMLElement>('[data-question-id]')?.dataset.questionId };
    }
    place(range.getBoundingClientRect());
    visible = true;
  }

  function ask() {
    app.markSeen('hint-select-passage');
    if (!pending) return;
    const { text, turnId, source, questionId, taskId, conceptId } = pending;
    app.quote = { text, turnId, source, questionId, taskId, conceptId, scrollY: stageScroll() };
    visible = false;
    window.getSelection()?.removeAllRanges();
    app.openPanel('questions');
    requestAnimationFrame(() => document.getElementById('question-input')?.focus());
  }

  function close() {
    visible = false;
    target = null;
    confirmRemove = false;
  }

  /** A clicked highlight's note is written or changed in the Notes tab, in the same box as every note. */
  function editNote() {
    if (!target) return;
    const { id } = target;
    close();
    app.showAnnotation(id, { edit: true });
  }

  /** The passage as a highlight would keep it: where it is, and which section it belongs to. */
  function passage(): NoteQuote | null {
    if (!pending) return null;
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
    if (!conceptId) return null;
    return {
      concept_id: conceptId,
      passage: pending.text,
      ...(pending.occurrence ? { occurrence: pending.occurrence } : {}),
      ...(source ? { source } : pending.taskId ? { task_id: pending.taskId } : { turn_id: pending.turnId }),
    };
  }

  function highlight() {
    app.markSeen('hint-select-passage');
    const quote = passage();
    if (!quote) return;
    close();
    window.getSelection()?.removeAllRanges();
    void app.annotate({ kind: 'highlight', ...quote });
  }

  // Like Ask: the passage goes into the Notes box, where the note is written with formulas and images like any other.
  function note() {
    app.markSeen('hint-select-passage');
    const quote = passage();
    if (!quote) return;
    close();
    window.getSelection()?.removeAllRanges();
    app.notePassage(quote);
    requestAnimationFrame(() => document.getElementById('section-note')?.focus());
  }

  // Removing a highlight that carries a note asks first, in the toolbar itself.
  let confirmRemove = $state(false);

  function remove() {
    if (!target) return;
    const { id, note: text } = target;
    if (text && !confirmRemove) {
      confirmRemove = true;
      return;
    }
    close();
    void app.removeAnnotation(id);
  }

  let settle: ReturnType<typeof setTimeout> | undefined;

  function onSelectionChange() {
    if (target) return;
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
  onkeydown={(e) => e.key === 'Escape' && visible && close()}
  onselectionchange={onSelectionChange}
/>
<!-- Scrolling moves the passage away from the toolbar, but a writing box scrolling its own text does not. -->
<svelte:window onscrollcapture={(e) => !(e.target instanceof Element && e.target.closest('.cm-editor')) && (visible = false)} />

{#if visible && target}
  <div bind:this={pop} class="pop bar" data-side={side} role="toolbar" aria-label={t("Your highlight")} style:left="{left}px" style:top="{top}px" style:--caret="{caret}px">
    {#if confirmRemove}
      <span class="asking">{t("Delete this note?")}</span>
      <!-- svelte-ignore a11y_autofocus -->
      <button class="danger" autofocus onpointerdown={(e) => e.preventDefault()} onclick={remove} onkeydown={(e) => e.key === 'Escape' && (confirmRemove = false)}>
        <span class="icon" aria-hidden="true">×</span>{t("Delete")}
      </button>
      <button onpointerdown={(e) => e.preventDefault()} onclick={() => (confirmRemove = false)}>{t("Cancel")}</button>
    {:else}
      <button onpointerdown={(e) => e.preventDefault()} onclick={editNote}>
        <span class="icon note" aria-hidden="true">✎</span>{target.note ? t("Edit note") : t("Add note")}
      </button>
      <button class="danger" onpointerdown={(e) => e.preventDefault()} onclick={remove}>
        <span class="icon" aria-hidden="true">×</span>{t("Remove highlight")}
      </button>
    {/if}
  </div>
{:else if visible}
  <div bind:this={pop} class="pop bar" data-side={side} role="toolbar" aria-label={t("Selected passage")} style:left="{left}px" style:top="{top}px" style:--caret="{caret}px">
    {#if annotatable}
      <button onpointerdown={(e) => e.preventDefault()} onclick={highlight}>
        <span class="icon swatch" aria-hidden="true"></span>{t("Highlight")}
      </button>
      <button onpointerdown={(e) => e.preventDefault()} onclick={note}>
        <span class="icon note" aria-hidden="true">✎</span>{t("Note")}
      </button>
    {/if}
    <button onpointerdown={(e) => e.preventDefault()} onclick={ask}>
      <span class="icon asked" aria-hidden="true">?</span>{t("Ask about this passage")}
    </button>
  </div>
{/if}

<style>
  .pop {
    animation: enter-pop var(--quick) var(--ease-out);
    position: fixed;
    z-index: 50;
    display: flex;
    border: 1px solid var(--rule-strong);
    border-radius: 8px;
    background: var(--raised);
    box-shadow: var(--shadow);
  }

  /* A small pointer from the toolbar to the passage it acts on. */
  .pop::after {
    content: '';
    position: absolute;
    left: calc(var(--caret) - 5px);
    width: 10px;
    height: 10px;
    border: 1px solid var(--rule-strong);
    background: var(--raised);
    rotate: 45deg;
  }

  .pop[data-side='above']::after {
    bottom: -6px;
    border-top: 0;
    border-left: 0;
  }

  .pop[data-side='below']::after {
    top: -6px;
    border-right: 0;
    border-bottom: 0;
  }

  .bar {
    align-items: center;
    padding: 0.2rem;
    gap: 0.1rem;
  }

  .bar > button {
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    height: 2rem;
    padding: 0 0.65rem 0 0.45rem;
    border: 0;
    border-radius: 6px;
    background: none;
    color: var(--ink);
    font-size: var(--step--1);
    font-weight: 500;
    white-space: nowrap;
    cursor: pointer;
  }

  .bar > button:hover,
  .bar > button:focus-visible {
    background: var(--accent-wash);
  }

  .bar > .asking {
    padding: 0 0.5rem 0 0.6rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
    white-space: nowrap;
  }

  .bar > button.danger:hover,
  .bar > button.danger:focus-visible {
    background: var(--danger-wash);
    color: var(--danger);
  }

  .bar > button + button::before {
    content: '';
    position: absolute;
    left: -0.1rem;
    top: 0.45rem;
    bottom: 0.45rem;
    width: 1px;
    background: var(--rule);
  }

  /* The same marks the margin uses for notes and questions, so each action shows what it leaves behind. */
  .icon {
    display: inline-grid;
    place-items: center;
    width: 1.15rem;
    height: 1.15rem;
    border-radius: 50% 50% 50% 3px;
    font-size: 0.7rem;
    font-weight: 700;
    line-height: 1;
    color: var(--pencil);
  }

  .icon.swatch {
    width: 0.95rem;
    height: 0.95rem;
    border-radius: 3px;
    background: var(--mine-wash);
    box-shadow: inset 0 0 0 1px var(--mine);
  }

  .icon.note {
    border: 1px solid var(--mine);
    background: var(--mine-wash);
    color: var(--ink);
  }

  .icon.asked {
    border: 1px solid #c9a82b;
    background: var(--marker);
    color: #2a2208;
  }

  .danger .icon {
    font-size: 1rem;
    font-weight: 400;
  }

</style>
