<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type PanelTab } from '../lib/store.svelte';
  import Questions from './Questions.svelte';
  import SourceViewer from './SourceViewer.svelte';
  import Notes from './Notes.svelte';
  import Memory from './Memory.svelte';

  // The top bar's toggles are the panel's only navigation; each view keeps its own scroll position between visits.
  const scroll: Record<string, number> = {};
  let body: HTMLElement | undefined = $state();
  let panel: HTMLElement | undefined = $state();
  const labels: Record<PanelTab, () => string> = {
    questions: () => t('Questions'),
    source: () => t('Source'),
    notes: () => t('Notes'),
    memory: () => t('Memory'),
  };

  let shown = app.panelTab;
  $effect.pre(() => {
    const tab = app.panelTab;
    if (tab === shown) return;
    if (body) scroll[shown] = body.scrollTop;
    shown = tab;
    requestAnimationFrame(() => body && (body.scrollTop = scroll[tab] ?? 0));
  });

  // Opening the panel moves focus into it, unless something there already took it (such as the question box);
  // closing it returns focus to the top-bar toggle when focus was inside, so keyboard users are not dropped on the page.
  let wasOpen = app.panelOpen;
  $effect.pre(() => {
    const open = app.panelOpen;
    if (open === wasOpen) return;
    wasOpen = open;
    const tab = app.panelTab;
    if (open) {
      requestAnimationFrame(() => {
        if (!panel?.contains(document.activeElement)) panel?.focus();
      });
    } else if (panel?.contains(document.activeElement)) {
      requestAnimationFrame(() => document.getElementById(`toggle-${tab}`)?.focus());
    }
  });

  function startResize(event: PointerEvent) {
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    const move = (e: PointerEvent) => app.resizePanel(window.innerWidth - e.clientX, true, false);
    // A drag can end without pointerup: the pointer is cancelled (a touch turned into a scroll) or capture is lost.
    const stop = () => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', stop);
      handle.removeEventListener('pointercancel', stop);
      handle.removeEventListener('lostpointercapture', stop);
      document.body.classList.remove('resizing');
      app.savePanelWidth();
    };
    document.body.classList.add('resizing');
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', stop);
    handle.addEventListener('pointercancel', stop);
    handle.addEventListener('lostpointercapture', stop);
  }

  function resizeByKey(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') app.resizePanel(app.panelWidth + 40);
    if (event.key === 'ArrowRight') app.resizePanel(app.panelWidth - 40);
  }
</script>

<aside id="auxiliary" class="panel" aria-label={labels[app.panelTab]()} hidden={!app.panelOpen} tabindex="-1" bind:this={panel}>
  <!-- A focusable window splitter is interactive per WAI-ARIA, which this lint rule does not model. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
  <div
    class="handle"
    role="separator"
    aria-orientation="vertical"
    aria-label={t("Resize panel")}
    aria-valuenow={app.panelWidth}
    aria-valuemin={320}
    tabindex="0"
    onpointerdown={startResize}
    onkeydown={resizeByKey}
  ></div>
  <button id="close-aux" class="btn btn-quiet close" onclick={() => (app.panelOpen = false)} aria-label={t("Close panel")} title={t("Close panel")}>
    <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
  </button>
  <div class="body" class:fill={app.panelTab === 'source'} bind:this={body}>
    <div class="view" id="panel-questions" hidden={app.panelTab !== 'questions'}><Questions /></div>
    <div class="view" id="panel-source" hidden={app.panelTab !== 'source'}><SourceViewer /></div>
    <div class="view" id="panel-notes" hidden={app.panelTab !== 'notes'}><Notes /></div>
    <div class="view" id="panel-memory" hidden={app.panelTab !== 'memory'}><Memory /></div>
  </div>
</aside>

<style>
  .panel {
    animation: enter-slide var(--settle) var(--ease-out);
    position: relative;
    display: flex;
    flex: none;
    flex-direction: column;
    width: var(--panel);
    border-left: 1px solid var(--rule);
    background: var(--sheet);
  }

  .panel:focus {
    outline: none;
  }

  .handle {
    position: absolute;
    top: 0;
    bottom: 0;
    left: -4px;
    z-index: 2;
    width: 8px;
    cursor: col-resize;
    touch-action: none;
  }

  .handle:hover,
  .handle:focus-visible {
    background: linear-gradient(90deg, transparent 3px, var(--accent) 3px 5px, transparent 5px);
  }

  :global(body.resizing) {
    cursor: col-resize;
    user-select: none;
  }

  /* The close button floats in the corner, level with the heading each view opens with. */
  .close {
    position: absolute;
    top: 0.7rem;
    right: 0.6rem;
    z-index: 2;
    padding-inline: 0.45rem;
    background: var(--sheet);
    color: var(--pencil);
  }

  /* A view that comes into view fades in rather than replacing the last one in a blink. */
  .view:not([hidden]) {
    animation: enter-fade var(--quick) ease;
  }

  /* The views carry the vertical padding, so a sticky header or composer inside one sits flush with the panel's edge. */
  .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0 1.1rem;
  }

  .view {
    padding: 1.1rem 0 3rem;
  }

  /* The reader scrolls inside itself, so the source tab fills the panel instead. */
  .body.fill {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .body.fill > .view {
    padding-bottom: 1rem;
  }

  .body.fill > .view:not([hidden]) {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  @media (max-width: 79.99rem) {
    .panel {
      position: fixed;
      top: var(--topbar);
      right: 0;
      bottom: 0;
      z-index: 30;
      width: min(var(--panel), 100vw);
      height: auto;
      box-shadow: var(--shadow);
    }
  }

  @media (max-width: 40rem) {
    .panel {
      width: 100vw;
      border-left: 0;
    }

    .handle {
      display: none;
    }
  }
</style>
