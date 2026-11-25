<script lang="ts">
  import { t, locale, diagnostic } from './lib/i18n.svelte';
  import { onMount, untrack } from 'svelte';
  import { app } from './lib/store.svelte';
  import { studio } from './lib/studio.svelte';
  import { panelCoversLesson } from './lib/media';
  import { scrollStageByKey } from './lib/stage';
  import TopBar from './components/TopBar.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import ConceptPage from './components/ConceptPage.svelte';
  import ChapterPage from './components/ChapterPage.svelte';
  import ReviewPage from './components/ReviewPage.svelte';
  import StudioPage from './components/StudioPage.svelte';
  import SidePanel from './components/SidePanel.svelte';
  import SelectionAsk from './components/SelectionAsk.svelte';
  import SettingsDialog from './components/SettingsDialog.svelte';
  import CitationPeek from './components/CitationPeek.svelte';
  import Help from './components/Help.svelte';
  import Search from './components/Search.svelte';
  import ErrorToast from './components/ErrorToast.svelte';
  import Library from './components/Library.svelte';
  import Welcome from './components/Welcome.svelte';

  onMount(() => {
    void app.sync().then(handOver);
    void app.loadSeen();
    app.connect();
    // A quiet check at launch: a newer version only marks Settings, and a failure shows nothing.
    app.checkForUpdate().catch(() => {});
    app.resumeUpdate().catch(() => {});
    // The update this tab waited for reloaded it: About says what was installed.
    if (app.updated) {
      app.settingsPane = 'about';
      app.settingsOpen = true;
    }
  });

  // A course action in the library asks this course's Studio: fill it in once the course has loaded.
  async function handOver() {
    // The stash names the course by its folder, which the library knows; it may not have loaded with the course.
    if (!app.library) await app.loadLibrary(true);
    const handed = app.takeStudioHandoff();
    if (!handed) return;
    // The chat that made this course carries on here; a request starts a new chat with it filled in.
    if (handed.thread) return app.showStudio({ thread: handed.thread, focus: true });
    app.drafts.set('studio:new', studio.handoff(handed.prompt));
    app.showStudio({ focus: true });
  }

  // Going to Studio and back returns Learn or Review to where the learner was on it. The stage is one scroller for every
  // place, so without this the page came back at whatever offset Studio had last been scrolled to.
  const place = $derived(
    app.libraryOpen ? 'library' : app.courseOpen ? 'studio' : app.reviewOpen ? 'review' : `learn:${app.viewingChapter ?? app.viewing ?? app.currentId}`,
  );
  // A reload reopens a course at the place the learner was in (Studio, Learn or Review), remembered in this browser per
  // course. Restoring comes first, so the first save after a load is the restored place, not Learn.
  let restoredFor = '';
  $effect(() => {
    const id = app.state?.course.id;
    if (!id || app.libraryOpen || restoredFor === id) return;
    restoredFor = id;
    untrack(() => {
      let saved = '';
      try {
        saved = localStorage.getItem(`place:${id}`) ?? '';
      } catch {
        // Without storage a reload opens Learn, as before.
      }
      if (app.courseOpen || app.reviewOpen) return;
      if (saved === 'studio') app.showCourse();
      else if (saved === 'review') app.showReview();
    });
  });
  $effect(() => {
    const id = app.state?.course.id;
    if (!id || app.libraryOpen || restoredFor !== id) return;
    const where = app.courseOpen ? 'studio' : app.reviewOpen ? 'review' : 'learn';
    try {
      localStorage.setItem(`place:${id}`, where);
    } catch {
      // The place is a convenience; nothing is lost without it.
    }
  });
  let scrolled = { place: '', top: 0 };
  let left: { place: string; top: number } | null = null;
  let shown = '';
  $effect(() => {
    if (!stage) return;
    const node = stage;
    const keep = () => (scrolled = { place: untrack(() => place), top: node.scrollTop });
    node.addEventListener('scroll', keep, { passive: true });
    return () => node.removeEventListener('scroll', keep);
  });
  $effect(() => {
    const now = place;
    untrack(() => {
      const before = shown;
      shown = now;
      if (now === 'studio' && before) left = { place: before, top: scrolled.place === before ? scrolled.top : 0 };
      else if (before === 'studio' && left?.place === now) stage?.scrollTo({ top: left.top, behavior: 'instant' });
    });
  });

  // The route folds when the reading column has no room beside it (an open side panel, a narrow window), and is a
  // drawer on a phone. The stage is measured rather than queried in CSS so the rail, its capsule and the grid agree.
  // It is measured for the width it is heading to: a docked side panel counts at its full width while it slides in or
  // out, so the route folds or unfolds as the panel starts to move rather than partway through.
  let stage = $state<HTMLElement>();
  let room = $state(Infinity);
  $effect(() => {
    if (!stage) return;
    const workspace = stage.parentElement!;
    const scrollbar = () => stage!.offsetWidth - stage!.clientWidth;
    const observer = new ResizeObserver(() => (room = workspace.clientWidth - scrollbar()));
    observer.observe(workspace);
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
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const docked = app.state && !app.libraryOpen && app.panelShown && !panelCoversLesson();
    app.stageNarrow = room - (docked ? app.panelWidth : 0) < 68.5 * rem;
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

  // Search opens with Shift pressed twice on its own, as in JetBrains IDEs, or with Ctrl+K (⌘K on a Mac).
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  let shiftAlone = false;
  let shiftAt = 0;
  const searchable = () => !!app.state && !app.libraryOpen && !app.searchOpen;

  function onKeyUp(event: KeyboardEvent) {
    if (event.key !== 'Shift' || !shiftAlone) return;
    shiftAlone = false;
    if (event.timeStamp - shiftAt < 400 && searchable()) {
      shiftAt = 0;
      app.searchOpen = true;
    } else shiftAt = event.timeStamp;
  }

  function onKey(event: KeyboardEvent) {
    shiftAlone = event.key === 'Shift' && !event.repeat && !event.ctrlKey && !event.metaKey && !event.altKey;
    if (event.key.toLowerCase() === 'k' && (mac ? event.metaKey : event.ctrlKey) && !event.altKey && !event.shiftKey && searchable()) {
      event.preventDefault();
      app.searchOpen = true;
      return;
    }
    if (event.key === 'Escape') {
      if (app.routeOpen) app.routeOpen = false;
      else if (app.libraryOpen && app.state && !(event.target as HTMLElement).closest('dialog')) app.libraryOpen = false;
      else if (app.panelShown && panelCoversLesson()) app.panelOpen = false;

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
    else if (event.key === 's') app.panelShown && app.panelTab === 'source' ? (app.panelOpen = false) : app.openPanel('source');
    else if (event.key === 'n') app.panelShown && app.panelTab === 'notes' ? (app.panelOpen = false) : app.openPanel('notes');
    else if (event.key === 'r') app.toggleRoute();
    else if (event.key === 'd') app.studioShown ? (app.courseOpen = false) : app.showStudio({ focus: true });
    else if (event.key === 'c') (document.getElementById('continue-step') as HTMLButtonElement | null)?.click();
    else if (event.key === '?') app.helpOpen = true;
  }
</script>

<svelte:window onkeydown={onKey} onkeyup={onKeyUp} onpointerdown={() => (shiftAlone = false)} />

<TopBar />

<!-- The stage scrolls on its own, so its scrollbar ends where the side panel begins. -->
<div class="workspace" style:--panel="{app.panelWidth}px">
<div id="stage" class="stage" bind:this={stage}>
<div class="layout" class:with-panel={app.panelShown} class:folded={app.folded && !app.libraryOpen} class:own-width={app.courseOpen || app.libraryOpen || app.reviewOpen}>
  {#if app.signedOut}
    <main id="main" class="loading" role="alert">
      <h1 class="signed-out">{t('Open Throughline from its launcher')}</h1>
      <p>{t('This browser is not signed in to Throughline. Open it from the Throughline launcher, or run "throughline open" in a terminal, and this page opens signed in. This keeps other people on this computer out of your courses.')}</p>
    </main>
  {:else if app.libraryOpen}
    <Library />
  {:else if app.state}
    <div class="scrim" class:visible={app.routeOpen} onclick={() => (app.routeOpen = false)} aria-hidden="true"></div>
    <!-- Studio shows the whole route in its chapter strip, and Review has its own scope picker, so the rail steps aside
         for those places. -->
    {#if !app.courseOpen && !app.reviewOpen}<RouteRail />{/if}
    <main id="main">
      {#if app.courseOpen}
        <StudioPage />
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
  {:else if app.stateError}
    <main id="main" class="loading" role="alert">
      <p class="problem">{t('This course could not be opened: {error}', { error: diagnostic(app.stateError) })}</p>
      <button class="btn btn-small" onclick={() => app.retryLoad()}>{t('Try again')}</button>
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
<Welcome />
<Search />
<ErrorToast />

<style>
  /* The side panel slides in and out past the window's edge, which must not scroll the window sideways. */
  .workspace {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: clip;
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
      grid-template-columns var(--move) var(--ease-in-out),
      column-gap var(--move) var(--ease-in-out),
      max-width var(--move) var(--ease-in-out);
  }

  @media (prefers-reduced-motion: reduce) {
    .layout {
      transition: none;
    }
  }

  /* Folded, the capsule sits at the stage's left edge and the reading column centres in the rest. */
  /* Studio, Review and the library set their own widths. */
  .layout.own-width {
    grid-template-columns: minmax(0, 1fr);
    max-width: none;
  }

  .layout.folded {
    grid-template-columns: var(--rail-folded) minmax(0, 1fr);
    column-gap: 0;
    max-width: 100vw;
  }

  .layout.own-width.folded {
    grid-template-columns: minmax(0, 1fr);
    max-width: none;
  }

  main {
    min-width: 0;
    padding: 2.5rem clamp(1rem, 4vw, 3.5rem) 6rem;
  }

  /* Studio fills the window, from just under the top bar to just above its bottom edge. */
  main:has(> :global(.page.filling)) {
    padding-block: 1.25rem;
  }

  .loading {
    grid-column: 1 / -1;
    color: var(--pencil);
    text-align: center;
  }

  .loading .problem {
    color: var(--danger);
  }

  .signed-out {
    margin-bottom: 0.6rem;
    color: var(--ink);
    font-size: var(--step-1);
  }

  .loading:has(.signed-out) p {
    max-width: 34rem;
    margin-inline: auto;
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

    .scrim {
      display: block;
      position: fixed;
      inset: var(--topbar) 0 0;
      z-index: 30;
      background: rgb(17 20 27 / 0.4);
      opacity: 0;
      visibility: hidden;
      transition:
        opacity var(--move) ease,
        visibility 0s linear var(--move);
    }

    .scrim.visible {
      opacity: 1;
      visibility: visible;
      transition:
        opacity var(--move) ease,
        visibility 0s;
    }
  }
</style>
