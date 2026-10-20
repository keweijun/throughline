<script lang="ts">
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
</script>

<aside id="auxiliary" class="panel" class:open={app.panelOpen} aria-label="Questions and sources" hidden={!app.panelOpen}>
  <div class="bar">
    <div class="tabs" role="tablist">
      <button role="tab" aria-selected={app.panelTab === 'questions'} onclick={() => select('questions')}>Questions</button>
      <button role="tab" aria-selected={app.panelTab === 'source'} onclick={() => select('source')}>Source</button>
    </div>
    <button id="close-aux" class="btn btn-quiet btn-small" onclick={() => (app.panelOpen = false)} aria-label="Close panel">Close</button>
  </div>
  <div class="body" bind:this={body}>
    <div hidden={app.panelTab !== 'questions'}><Questions /></div>
    <div hidden={app.panelTab !== 'source'}><SourceViewer /></div>
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
    overflow-y: auto;
    padding: 1.25rem 1.1rem 3rem;
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
  }
</style>
