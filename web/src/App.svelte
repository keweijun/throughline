<script lang="ts">
  import { t, locale } from './lib/i18n.svelte';
  import { onMount } from 'svelte';
  import { app } from './lib/store.svelte';
  import { panelCoversLesson } from './lib/media';
  import { scrollStageByKey } from './lib/stage';
  import TopBar from './components/TopBar.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import ConceptPage from './components/ConceptPage.svelte';
  import ChapterPage from './components/ChapterPage.svelte';
  import ReviewPage from './components/ReviewPage.svelte';
  import CoursePage from './components/CoursePage.svelte';
  import SidePanel from './components/SidePanel.svelte';
  import SelectionAsk from './components/SelectionAsk.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';
  import CitationPeek from './components/CitationPeek.svelte';
  import Help from './components/Help.svelte';
  import Toasts from './components/Toasts.svelte';
  import Library from './components/Library.svelte';

  onMount(() => {
    void app.sync();
    void app.loadSeen();
    app.connect();
    // A quiet check at launch: a newer version only marks Settings, and a failure shows nothing.
    app.checkForUpdate().catch(() => {});
  });

  // The route folds when the reading column has no room beside it (an open side panel, a narrow window), and is a
  // drawer on a phone. The stage is measured rather than queried in CSS so the rail, its capsule and the grid agree.
  let stage = $state<HTMLElement>();
  $effect(() => {
    if (!stage) return;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const observer = new ResizeObserver(([entry]) => (app.stageNarrow = entry.contentRect.width < 66 * rem));
    observer.observe(stage);
    const phone = matchMedia('(max-width: 56rem)');
    const update = () => (app.phone = phone.matches);
    update();
    phone.addEventListener('change', update);
    return () => {
      observer.disconnect();
      phone.removeEventListener('change', update);
    };
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
    else if (event.key === 'r') app.toggleRoute();
    else if (event.key === 'm') app.courseOpen && app.coursePart === 'memory' ? (app.courseOpen = false) : app.showCourse('memory');
    else if (event.key === 'd') app.studioShown ? (app.courseOpen = false) : app.showStudio();
    else if (event.key === 'c') (document.getElementById('continue-step') as HTMLButtonElement | null)?.click();
    else if (event.key === '?') app.helpOpen = true;
  }
</script>

<svelte:window onkeydown={onKey} />

<TopBar />

<!-- The stage scrolls on its own, so its scrollbar ends where the side panel begins. -->
<div class="workspace" style:--panel="{app.panelWidth}px">
<div id="stage" class="stage" bind:this={stage}>
<div class="layout" class:with-panel={app.panelOpen} class:folded={app.folded && !app.libraryOpen}>
  {#if app.libraryOpen}
    <Library />
  {:else if app.state}
    <div class="scrim" class:visible={app.routeOpen} onclick={() => (app.routeOpen = false)} aria-hidden="true"></div>
    <RouteRail />
    <main id="main">
      {#if app.courseOpen}
        <CoursePage />
      {:else if app.reviewOpen}
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
<Help />
<Toasts />

<style>
  .workspace {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  /* The stable gutter keeps the centred layout from shifting when a page is too short to scroll. */
  .stage {
    flex: 1;
    min-width: 0;
    overflow-x: hidden;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  /* The rail sits beside the reading column, and the two are centred together rather than drifting apart. */
  /* Folding and unfolding the route slides the reading column rather than jumping it. */
  .layout {
    display: grid;
    grid-template-columns: var(--rail) minmax(0, 1fr);
    column-gap: clamp(1rem, 3vw, 3rem);
    align-items: start;
    max-width: calc(var(--rail) + var(--measure) + 12rem);
    margin-inline: auto;
    transition:
      grid-template-columns var(--settle) var(--ease-out),
      column-gap var(--settle) var(--ease-out),
      max-width var(--settle) var(--ease-out);
  }

  @media (prefers-reduced-motion: reduce) {
    .layout {
      transition: none;
    }
  }

  /* Folded, the capsule sits at the stage's left edge and the reading column centres in the rest. */
  .layout.folded {
    grid-template-columns: var(--rail-folded) minmax(0, 1fr);
    column-gap: 0;
    max-width: 100vw;
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
