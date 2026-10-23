<script lang="ts">
  import { t, locale, diagnostic } from './lib/i18n.svelte';
  import { onMount } from 'svelte';
  import { app } from './lib/store.svelte';
  import TopBar from './components/TopBar.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import ConceptPage from './components/ConceptPage.svelte';
  import SidePanel from './components/SidePanel.svelte';
  import SelectionAsk from './components/SelectionAsk.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';
  import CitationPeek from './components/CitationPeek.svelte';
  import Shortcuts from './components/Shortcuts.svelte';
  import Library from './components/Library.svelte';

  onMount(() => {
    void app.load();
    app.connect();
  });

  $effect(() => {
    document.documentElement.lang = locale.language;
    document.title = app.state && !app.libraryOpen ? `${app.state.course.title} · ${t('Throughline')}` : t('Throughline');
  });

  function step(offset: number) {
    const route = app.state?.curriculum.route ?? [];
    const next = route[route.indexOf(app.viewingId ?? '') + offset];
    if (next) app.view(next);
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (app.routeOpen) app.routeOpen = false;
      else if (app.panelOpen && matchMedia('(max-width: 79.99rem)').matches) app.panelOpen = false;
      return;
    }
    const target = event.target as HTMLElement;
    if (app.libraryOpen || event.metaKey || event.ctrlKey || event.altKey || target.closest('input, textarea, select, [contenteditable], dialog')) return;
    if (event.key === '/') {
      event.preventDefault();
      app.openPanel('questions');
      requestAnimationFrame(() => document.getElementById('question-input')?.focus());
    } else if (event.key === '[') step(-1);
    else if (event.key === ']') step(1);
    else if (event.key === 's') app.panelOpen && app.panelTab === 'source' ? (app.panelOpen = false) : app.openPanel('source');
    else if (event.key === '?') app.shortcutsOpen = true;
  }
</script>

<svelte:window onkeydown={onKey} />

<TopBar />

{#if app.error}
  <div class="banner" role="alert">
    <p>{diagnostic(app.error)}</p>
    <button class="btn btn-quiet btn-small" onclick={() => (app.error = null)}>{t("Dismiss")}</button>
  </div>
{/if}

{#if app.notice}
  <div class="banner notice" role="status">
    <p>{app.notice}</p>
    <button class="btn btn-quiet btn-small" onclick={() => (app.notice = null)}>{t("Dismiss")}</button>
  </div>
{/if}

<div class="layout" class:with-panel={app.panelOpen} style:--panel="{app.panelWidth}px">
  {#if app.libraryOpen}
    <Library />
  {:else if app.state}
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
      <p>{t("Opening your course…")}</p>
    </main>
  {/if}
</div>

<SelectionAsk />
<SettingsDialog />
<CitationPeek />
<Shortcuts />

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

  .banner.notice {
    background: var(--raised);
    color: var(--ink-soft);
  }

  .layout {
    display: grid;
    grid-template-columns: var(--rail) minmax(0, 1fr);
    align-items: start;
    max-width: 84rem;
    margin-inline: auto;
  }

  .layout.with-panel {
    max-width: none;
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
