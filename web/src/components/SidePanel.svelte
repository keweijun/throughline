<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type PanelTab } from '../lib/store.svelte';
  import Questions from './Questions.svelte';
  import SourceViewer from './SourceViewer.svelte';
  import Notes from './Notes.svelte';

  // Each tab keeps its own scroll position when you switch between them.
  const scroll: Record<string, number> = {};
  let body: HTMLElement | undefined = $state();
  let panel: HTMLElement | undefined = $state();
  const tabs: { id: PanelTab; label: () => string }[] = [
    { id: 'questions', label: () => t('Questions') },
    { id: 'source', label: () => t('Source') },
    { id: 'notes', label: () => t('Notes') },
  ];

  function select(tab: PanelTab) {
    if (body) scroll[app.panelTab] = body.scrollTop;
    app.panelTab = tab;
    requestAnimationFrame(() => body && (body.scrollTop = scroll[tab] ?? 0));
  }

  // Tabs follow the WAI-ARIA pattern: one tab stop, arrow keys (and Home/End) move between tabs.
  function tabKey(event: KeyboardEvent) {
    const index = tabs.findIndex((tab) => tab.id === app.panelTab);
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1 }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const tab = tabs[(next + tabs.length) % tabs.length].id;
    select(tab);
    document.getElementById(`panel-tab-${tab}`)?.focus();
  }

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
        if (!panel?.contains(document.activeElement)) document.getElementById(`panel-tab-${tab}`)?.focus();
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

<aside id="auxiliary" class="panel" aria-label={t("Questions and sources")} hidden={!app.panelOpen} bind:this={panel}>
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
    <div class="tabs" role="tablist" aria-label={t("Questions and sources")} tabindex="-1" onkeydown={tabKey}>
      {#each tabs as tab (tab.id)}
        <button
          role="tab"
          id="panel-tab-{tab.id}"
          aria-selected={app.panelTab === tab.id}
          aria-controls="panel-{tab.id}"
          tabindex={app.panelTab === tab.id ? 0 : -1}
          onclick={() => select(tab.id)}
        >{tab.label()}</button>
      {/each}
    </div>
    <button id="close-aux" class="btn btn-quiet btn-small" onclick={() => (app.panelOpen = false)} aria-label={t("Close panel")}>{t("Close")}</button>
  </div>
  <div class="body" class:fill={app.panelTab === 'source'} bind:this={body}>
    <div class="tab" role="tabpanel" id="panel-questions" aria-labelledby="panel-tab-questions" hidden={app.panelTab !== 'questions'}><Questions /></div>
    <div class="tab" role="tabpanel" id="panel-source" aria-labelledby="panel-tab-source" hidden={app.panelTab !== 'source'}><SourceViewer /></div>
    <div class="tab" role="tabpanel" id="panel-notes" aria-labelledby="panel-tab-notes" hidden={app.panelTab !== 'notes'}><Notes /></div>

  </div>
</aside>

<style>
  .panel {
    animation: enter-slide var(--settle) var(--ease-out);
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

  /* A tab that comes into view fades in rather than replacing the last one in a blink. */
  .tab:not([hidden]) {
    animation: enter-fade var(--quick) ease;
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
