<script lang="ts">
  import { onMount } from 'svelte';
  import { app } from './lib/store.svelte';
  import TopBar from './components/TopBar.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import ConceptPage from './components/ConceptPage.svelte';
  import SidePanel from './components/SidePanel.svelte';
  import SelectionAsk from './components/SelectionAsk.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';

  onMount(() => {
    void app.load();
    app.connect();
  });

  $effect(() => {
    document.title = app.state ? `${app.state.course.title} · Guided Learning` : 'Guided Learning';
  });

  function onKey(event: KeyboardEvent) {
    if (event.key !== 'Escape') return;
    if (app.routeOpen) app.routeOpen = false;
    else if (app.panelOpen && matchMedia('(max-width: 79.99rem)').matches) app.panelOpen = false;
  }
</script>

<svelte:window onkeydown={onKey} />

<TopBar />

{#if app.error}
  <div class="banner" role="alert">
    <p>{app.error}</p>
    <button class="btn btn-quiet btn-small" onclick={() => (app.error = null)}>Dismiss</button>
  </div>
{/if}

<div class="layout" class:with-panel={app.panelOpen}>
  {#if app.state}
    <div class="scrim" class:visible={app.routeOpen} onclick={() => (app.routeOpen = false)} aria-hidden="true"></div>
    <RouteRail />
    <main id="main">
      {#key app.viewingId}
        <ConceptPage conceptId={app.viewingId} />
      {/key}
    </main>
    <SidePanel />
  {:else if !app.error}
    <main id="main" class="loading" aria-busy="true">
      <p>Opening your course…</p>
    </main>
  {/if}
</div>

<SelectionAsk />
<SettingsDialog />

<style>
  .banner {
    position: sticky;
    top: var(--topbar);
    z-index: 25;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.55rem clamp(1rem, 3vw, 2rem);
    background: var(--danger-wash);
    color: var(--danger);
    border-bottom: 1px solid var(--rule);
    font-size: var(--step-0);
  }

  .layout {
    display: grid;
    grid-template-columns: var(--rail) minmax(0, 1fr);
    align-items: start;
    max-width: 100rem;
    margin-inline: auto;
  }

  .layout.with-panel {
    grid-template-columns: var(--rail) minmax(0, 1fr) var(--panel);
  }

  main {
    min-width: 0;
    padding: 2.5rem clamp(1rem, 4vw, 3.5rem) 6rem;
  }

  .loading {
    grid-column: 1 / -1;
    color: var(--pencil);
    text-align: center;
  }

  .scrim {
    display: none;
  }

  @media (max-width: 79.99rem) {
    .layout.with-panel {
      grid-template-columns: var(--rail) minmax(0, 1fr);
    }
  }

  @media (max-width: 56rem) {
    .layout,
    .layout.with-panel {
      grid-template-columns: minmax(0, 1fr);
    }

    main {
      padding-top: 1.5rem;
    }

    .scrim.visible {
      display: block;
      position: fixed;
      inset: var(--topbar) 0 0;
      z-index: 30;
      background: rgb(17 20 27 / 0.4);
    }
  }
</style>
