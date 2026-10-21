<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import Questions from './Questions.svelte';
  import SourceViewer from './SourceViewer.svelte';

  // Each tab keeps its own scroll position when you switch between them.
  const scroll: Record<string, number> = {};
  let body: HTMLElement | undefined = $state();

  function select(tab: 'questions' | 'source') {
    if (body) scroll[app.panelTab] = body.scrollTop;
    app.panelTab = tab;
    requestAnimationFrame(() => body && (body.scrollTop = scroll[tab] ?? 0));
  }

  function startResize(event: PointerEvent) {
    const handle = event.currentTarget as HTMLElement;
    handle.setPointerCapture(event.pointerId);
    const move = (e: PointerEvent) => app.resizePanel(window.innerWidth - e.clientX);
    const stop = () => {
      handle.removeEventListener('pointermove', move);
      document.body.classList.remove('resizing');
    };
    document.body.classList.add('resizing');
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', stop, { once: true });
  }

  function resizeByKey(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') app.resizePanel(app.panelWidth + 40);
    if (event.key === 'ArrowRight') app.resizePanel(app.panelWidth - 40);
  }
</script>

<aside id="auxiliary" class="panel" aria-label={t("Questions and sources")} hidden={!app.panelOpen}>
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
  <div class="bar">
    <div class="tabs" role="tablist">
      <button role="tab" aria-selected={app.panelTab === 'questions'} onclick={() => select('questions')}>{t("Questions")}</button>
      <button role="tab" aria-selected={app.panelTab === 'source'} onclick={() => select('source')}>{t("Source")}</button>
    </div>
    <button id="close-aux" class="btn btn-quiet btn-small" onclick={() => (app.panelOpen = false)} aria-label={t("Close panel")}>{t("Close")}</button>
  </div>
  <div class="body" class:fill={app.panelTab === 'source'} bind:this={body}>
    <div class="tab" hidden={app.panelTab !== 'questions'}><Questions /></div>
    <div class="tab" hidden={app.panelTab !== 'source'}><SourceViewer /></div>
  </div>
</aside>

<style>
  .panel {
    position: sticky;
    top: var(--topbar);
    display: flex;
    flex-direction: column;
    height: calc(100vh - var(--topbar));
    border-left: 1px solid var(--rule);
    background: var(--sheet);
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

  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.6rem 0.75rem 0 1rem;
    border-bottom: 1px solid var(--rule);
  }

  .tabs {
    display: flex;
    gap: 1rem;
  }

  [role='tab'] {
    padding: 0.5rem 0.1rem 0.6rem;
    border: 0;
    border-bottom: 2px solid transparent;
    background: none;
    font-size: var(--step-0);
    font-weight: 500;
    color: var(--pencil);
    cursor: pointer;
  }

  [role='tab'][aria-selected='true'] {
    color: var(--ink);
    border-bottom-color: var(--accent);
  }

  .body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 1.25rem 1.1rem 3rem;
  }

  /* The reader scrolls inside itself, so the source tab fills the panel instead. */
  .body.fill {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding-bottom: 1rem;
  }

  .body.fill > .tab:not([hidden]) {
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
