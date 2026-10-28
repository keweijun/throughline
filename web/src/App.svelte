<script lang="ts">
  import { t, locale, diagnostic } from './lib/i18n.svelte';
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { app } from './lib/store.svelte';
  import { panelCoversLesson } from './lib/media';
  import { scrollStageByKey } from './lib/stage';
  import TopBar from './components/TopBar.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import ConceptPage from './components/ConceptPage.svelte';
  import ChapterPage from './components/ChapterPage.svelte';
  import ReviewPage from './components/ReviewPage.svelte';
  import SidePanel from './components/SidePanel.svelte';
  import SelectionAsk from './components/SelectionAsk.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';
  import CitationPeek from './components/CitationPeek.svelte';
  import Shortcuts from './components/Shortcuts.svelte';
  import Library from './components/Library.svelte';
  import RememberPrompt from './components/RememberPrompt.svelte';

  onMount(() => {
    void app.sync();
    app.connect();
  });

  $effect(() => {
    document.documentElement.lang = locale.language;
    document.title = app.state && !app.libraryOpen ? `${app.state.course.title} · ${t('Throughline')}` : t('Throughline');
  });

  const suggestion = $derived(app.libraryOpen ? undefined : app.state?.memory?.find((e) => e.status === 'suggested'));

  function step(offset: number) {
    const route = app.state?.curriculum.route ?? [];
    const next = route[route.indexOf(app.viewingId ?? '') + offset];
    if (next) app.view(next);
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (app.routeOpen) app.routeOpen = false;
      else if (app.libraryOpen && app.state && !(event.target as HTMLElement).closest('dialog')) app.libraryOpen = false;
      else if (app.panelOpen && panelCoversLesson()) app.panelOpen = false;

      return;
    }
    if (scrollStageByKey(event)) return;
    const target = event.target as HTMLElement;
    if (app.libraryOpen || event.metaKey || event.ctrlKey || event.altKey || target.closest('input, textarea, select, [contenteditable], dialog')) return;
    if (event.key === '/') {
      event.preventDefault();
      app.openPanel('questions');
      requestAnimationFrame(() => document.getElementById('question-input')?.focus());
    } else if (event.key === '[') step(-1);
    else if (event.key === ']') step(1);
    else if (event.key === 's') app.panelOpen && app.panelTab === 'source' ? (app.panelOpen = false) : app.openPanel('source');
    else if (event.key === 'n') app.panelOpen && app.panelTab === 'notes' ? (app.panelOpen = false) : app.openPanel('notes');
    else if (event.key === 'm') app.panelOpen && app.panelTab === 'memory' ? (app.panelOpen = false) : app.openPanel('memory');
    else if (event.key === 'c') (document.getElementById('continue-step') as HTMLButtonElement | null)?.click();
    else if (event.key === '?') app.shortcutsOpen = true;
  }
</script>

<svelte:window onkeydown={onKey} />

<TopBar />

{#if app.error}
  <div class="banner" role="alert" out:fade={{ duration: 160 }}>
    <p>{diagnostic(app.error)}</p>
    <button class="btn btn-quiet btn-small" onclick={() => (app.error = null)}>{t("Dismiss")}</button>
  </div>
{/if}

{#if app.notice}
  <div class="banner notice" role="status" out:fade={{ duration: 160 }}>
    <p>{app.notice}</p>
    <button class="btn btn-quiet btn-small" onclick={() => (app.notice = null)}>{t("Dismiss")}</button>
  </div>
{/if}

<!-- A preference the teacher suggested takes effect only once the learner confirms it (ADR 0010). -->
{#if suggestion && !(app.panelOpen && app.panelTab === 'memory')}
  <div class="banner notice" role="status" out:fade={{ duration: 160 }}>
    <RememberPrompt entry={suggestion} />
  </div>
{/if}

<!-- The stage scrolls on its own, so its scrollbar ends where the side panel begins. -->
<div class="workspace" style:--panel="{app.panelWidth}px">
<div id="stage" class="stage">
<div class="layout" class:with-panel={app.panelOpen}>
  {#if app.libraryOpen}
    <Library />
  {:else if app.state}
    <div class="scrim" class:visible={app.routeOpen} onclick={() => (app.routeOpen = false)} aria-hidden="true"></div>
    <RouteRail />
    <main id="main">
      {#if app.reviewOpen}
        <ReviewPage />
      {:else if app.viewingChapter}
        {#key app.viewingChapter}
          <ChapterPage chapterId={app.viewingChapter} />
        {/key}
      {:else}
        {#key app.viewingId}
          <ConceptPage conceptId={app.viewingId} />
        {/key}
      {/if}
    </main>
  {:else if !app.error}
    <main id="main" class="loading" aria-busy="true">
      <p>{t("Opening your course…")}</p>
    </main>
  {/if}
</div>
</div>
{#if app.state && !app.libraryOpen}
  <SidePanel />
{/if}
</div>

<SelectionAsk />
<SettingsDialog />
<CitationPeek />
<Shortcuts />

<style>
  .banner {
    animation: enter-drop var(--settle) var(--ease-out);
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

  .workspace {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  /* The stable gutter keeps the centred layout from shifting when a page is too short to scroll. The rail folds to its
     route markers when the stage is narrower than the rail and a reading column, so the lesson keeps its width. */
  .stage {
    container: stage / inline-size;
    flex: 1;
    min-width: 0;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  /* The rail sits beside the reading column, and the two are centred together rather than drifting apart. */
  .layout {
    display: grid;
    grid-template-columns: var(--rail) minmax(0, 1fr);
    align-items: start;
    max-width: calc(var(--rail) + var(--measure) + 9rem);
    margin-inline: auto;
  }

  @media (min-width: 56.01rem) {
    @container stage (max-width: 64rem) {
      .layout {
        grid-template-columns: var(--rail-folded) minmax(0, 1fr);
      }
    }
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
