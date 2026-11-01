<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type PanelTab } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';
  import type { LibraryCourse } from '../lib/types';

  const studying = $derived(!!app.state && !app.libraryOpen);
  // Whether Codex is already busy in this course's Studio, say in a chat left running before a reload; asking does not
  // start Codex. Events keep it current from then on.
  let activityAsked = false;
  $effect(() => {
    if (studying && !activityAsked) {
      activityAsked = true;
      void studio.loadActivity();
    }
  });
  const openQuestions = $derived(
    (app.state?.questions ?? []).filter((q) => q.status === 'unanswered' || q.status === 'suggested' || (q.choice === 'accept' && !q.returned)).length,
  );

  const suggested = $derived((app.state?.memory ?? []).filter((e) => e.status === 'suggested').length);

  // Study, Review or the course's Overview: the reading column shows one of them.
  const place = $derived(app.courseOpen ? 'overview' : app.reviewOpen ? 'review' : 'study');

  // The course switcher lists the library's other courses that can be opened, the open one first.
  let menuOpen = $state(false);
  let switcher = $state<HTMLElement>();
  const others = $derived(
    (app.library?.courses ?? [])
      .filter((c) => !c.error && c.concepts)
      .sort((a, b) => Number(b.path === app.library?.active) - Number(a.path === app.library?.active)),
  );
  function toggleMenu() {
    menuOpen = !menuOpen;
    if (menuOpen) void app.loadLibrary(true);
  }
  function switchTo(course: LibraryCourse) {
    menuOpen = false;
    if (course.path === app.library?.active) app.libraryOpen = false;
    else void app.openCourse(course.name);
  }
  // The menu closes on a click outside it or on Escape, as menus do.
  $effect(() => {
    if (!menuOpen) return;
    const away = (event: Event) => switcher && !switcher.contains(event.target as Node) && (menuOpen = false);
    const escape = (event: KeyboardEvent) => event.key === 'Escape' && (menuOpen = false);
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', escape);
    };
  });

  // Review is always there while studying, with no count: nothing comes due; the learner asks for a set (ADR 0014).
  const review = $derived(app.state?.review);

  // The side panel's views are switched only from here: picking another view swaps it, picking the open one closes the panel.
  const showing = (tab: PanelTab) => studying && app.panelOpen && app.panelTab === tab;
  function toggle(tab: PanelTab) {
    if (showing(tab)) app.panelOpen = false;
    else app.openPanel(tab);
  }
</script>

<header class="topbar">
  <div class="start">
  {#if studying}
  <button
    class="btn btn-quiet menu"
    aria-label={t("Course contents")}
    aria-expanded={app.routeOpen}
    aria-controls="route"
    onclick={() => (app.routeOpen = !app.routeOpen)}
  >
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg>
  </button>
  {/if}

  <!-- Where you are, from the widest place in: all courses › this course, which switches to another course (ADR 0017). -->
  <nav class="where" aria-label={t("Where you are")}>
    <button id="open-courses" class="crumb home" aria-current={app.libraryOpen ? 'page' : undefined} onclick={() => app.showLibrary()} title={t("All courses")}>
      <svg class="mark" viewBox="0 0 32 32" width="26" height="26" aria-hidden="true"><rect width="32" height="32" rx="7.5" fill="#24366e" /><path d="M6.5 9.2c3.4-1.5 6.6-1.5 9 0v15.6c-2.4-1.5-5.6-1.5-9 0z" fill="#fbfcfd" opacity=".78" /><path d="M16.5 9.2c2.4-1.5 5.6-1.5 9 0v15.6c-3.4-1.5-6.6-1.5-9 0z" fill="#fbfcfd" /><path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#24366e" stroke-width="4.6" stroke-linecap="round" /><path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#f0d25c" stroke-width="2.5" stroke-linecap="round" /></svg>
      <span class="wide-only">{t("All courses")}</span>
    </button>
    {#if app.state && !app.libraryOpen}
      <span class="sep" aria-hidden="true">›</span>
      <div class="switch" bind:this={switcher}>
        <button
          id="course-switcher"
          class="crumb course"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          title={t("Switch course")}
          onclick={toggleMenu}
        >
          <span class="name">{app.state.course.title}</span>
          <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5.5 8l4.5 4.5L14.5 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </button>
        {#if menuOpen}
          <ul class="course-menu" role="menu" aria-label={t("Switch course")}>
            {#each others as course (course.path)}
              <li role="none">
                <button role="menuitem" class:active={course.path === app.library?.active} onclick={() => switchTo(course)}>
                  <span class="title">{course.title ?? course.name}</span>
                  {#if course.current}<span class="meta">{course.current}</span>{/if}
                </button>
              </li>
            {/each}
            <li role="none" class="all">
              <button role="menuitem" onclick={() => ((menuOpen = false), app.showLibrary())}>{t("All courses")}</button>
            </li>
          </ul>
        {/if}
      </div>
    {:else if !app.libraryOpen}
      <span class="course">{t("Throughline")}</span>
    {/if}
  </nav>
  </div>

  {#if studying}
    <!-- The three places of one course, centred in the bar; the one you are in is always marked, so the way back is always the same. -->
    <div class="places" role="group" aria-label={t("This course")}>
      <button
        id="open-course"
        class="place" aria-label={t("Overview")}
        aria-current={place === 'overview' ? 'page' : undefined}
        title={t("This course: changing it, what the teacher remembers, sources and notes (m)")}
        onclick={() => app.showCourse()}
      >
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 3h6v6H3zM11 3h6v6h-6zM3 11h6v6H3zM11 11h6v6h-6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg><span class="wide-only">{t("Overview")}</span>{#if suggested}<span class="dot" aria-label={t("A preference to confirm")}></span>{/if}
      </button>
      <button id="open-study" class="place" aria-label={t("Learn")} aria-current={place === 'study' ? 'page' : undefined} onclick={() => ((app.courseOpen = false), (app.reviewOpen = false))}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 4.5c2.5-1 5-1 7 .5v11c-2-1.5-4.5-1.5-7-.5zM17 4.5c-2.5-1-5-1-7 .5v11c2-1.5 4.5-1.5 7-.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg><span class="wide-only">{t("Learn")}</span>
      </button>
      {#if review}
        <button
          id="open-review"
          class="place" aria-label={t("Review")}
          aria-current={place === 'review' ? 'page' : undefined}
          title={t("Answer questions from memory on what you have studied")}
          onclick={() => app.showReview()}
        >
          <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M15.5 10a5.5 5.5 0 1 1-1.6-3.9M14.5 3v3.4h-3.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg><span class="wide-only">{t("Review")}</span>
        </button>
      {/if}
    </div>
  {/if}

  <div class="actions">
    {#if app.connection !== 'live' && !(app.updating && !app.updating.failed)}
      <span class="chip chip-caution" role="status">
        {app.connection === 'connecting' ? t("Connecting…") : t("Reconnecting · your work is saved")}
      </span>
    {/if}
    {#if studying}
      <div class="switcher" class:open={app.panelOpen} role="group" aria-label={t("Questions and sources")}>
      <button id="toggle-questions" class="btn btn-quiet" aria-label={t("Questions")} aria-controls="auxiliary" aria-pressed={showing('questions')} onclick={() => toggle('questions')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 4.5h12v8.5H9l-3.5 3v-3H4z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg><span class="wide-only">{t("Questions")}</span>{#if openQuestions}<span class="count">{openQuestions}</span>{/if}
      </button>
      <button id="toggle-source" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('source')} aria-label={t("Source")} title={t("Source reader (s)")} onclick={() => toggle('source')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 4.5c2.5-1 5-1 7 .5v11c-2-1.5-4.5-1.5-7-.5zM17 4.5c-2.5-1-5-1-7 .5v11c2-1.5 4.5-1.5 7-.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Source")}</span>
      </button>
      <button id="toggle-notes" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('notes')} aria-label={t("Notes")} onclick={() => toggle('notes')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M13.5 3.5l3 3-9 9H4.5v-3zM11.5 5.5l3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Notes")}</span>
      </button>
      </div>
    {/if}
    {#if studying && !app.studioShown && (studio.waiting.length || studio.working.length)}
      <!-- What Codex is doing in Studio, on every page; the question itself stays in Studio's transcript. -->
      <button
        class="btn btn-small studio-status"
        class:needs={studio.waiting.length > 0}
        onclick={() => app.showStudio({ thread: studio.attention })}
        title={studio.waiting.length ? t("Codex is waiting for your answer in Studio") : t("Codex is working on your course in Studio")}
      >
        <span class="pulse" aria-hidden="true"></span>
        <span>{studio.waiting.length ? t("Studio needs you") : t("Studio working…")}</span>
      </button>
    {/if}
    {#if app.updating && !app.updating.failed}
      <!-- The host is expected to go away while Codex installs; this replaces the reconnecting notice. -->
      <button
        class="btn btn-small update"
        onclick={() => {
          app.settingsPane = 'about';
          app.settingsOpen = true;
        }}
        title={t("Codex is installing version {version}. Throughline comes back by itself.", { version: app.updating.to })}
      >
        <span class="pulse" aria-hidden="true"></span>
        <span>{t("Updating · {percent}%", { percent: Math.round(app.updating.progress) })}</span>
      </button>
    {:else if app.update?.available}
      <!-- Noticeable but quiet: a small pill that waits beside Settings, never a banner or a toast. -->
      <button
        class="btn btn-small update"
        onclick={() => {
          app.settingsPane = 'about';
          app.settingsOpen = true;
        }}
        title={t("Version {latest} is available. Open About to update.", { latest: app.update.latest })}
      >
        <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M12 19V6M6.5 11.5 12 6l5.5 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Update available")}</span>
      </button>
    {/if}
    <button id="open-settings" class="btn btn-quiet icon" onclick={() => (app.settingsOpen = true)} aria-label={t("Settings")} title={t("Settings: teacher, appearance and about")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M16.02 8.14L18.08 8.61L18.08 11.39L16.02 11.86L15.57 12.94L16.70 14.73L14.73 16.70L12.94 15.57L11.86 16.02L11.39 18.08L8.61 18.08L8.14 16.02L7.06 15.57L5.27 16.70L3.30 14.73L4.43 12.94L3.98 11.86L1.92 11.39L1.92 8.61L3.98 8.14L4.43 7.06L3.30 5.27L5.27 3.30L7.06 4.43L8.14 3.98L8.61 1.92L11.39 1.92L11.86 3.98L12.94 4.43L14.73 3.30L16.70 5.27L15.57 7.06Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" /><circle cx="10" cy="10" r="2.5" fill="none" stroke="currentColor" stroke-width="1.4" /></svg>
    </button>
    <button id="open-help" class="btn btn-quiet icon shortcuts" onclick={() => (app.helpOpen = true)} aria-label={t("Help")} title={t("Help and keyboard shortcuts (?)")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="7.6" fill="none" stroke="currentColor" stroke-width="1.4" /><path d="M7.8 7.9a2.3 2.3 0 1 1 3.3 2.1c-.7.3-1.1.9-1.1 1.6v.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /><circle cx="10" cy="14.4" r=".95" fill="currentColor" /></svg>
    </button>
  </div>
</header>

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: 40;
    /* Three columns of equal sides, so the course's places sit in the middle of the window whatever the sides hold. */
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: center;
    gap: 1.25rem;
    height: var(--topbar);
    padding: 0 clamp(0.75rem, 2vw, 1.5rem);
    background: color-mix(in srgb, var(--ground) 88%, transparent);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--rule);
  }

  .start {
    grid-column: 1;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  .menu {
    display: none;
  }

  /* All courses › this course: a breadcrumb, quiet until pointed at, with the open place in ink. */
  .where {
    display: flex;
    flex: 0 1 auto;
    align-items: center;
    gap: 0.15rem;
    min-width: 0;
  }

  .crumb {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
    padding: 0.3rem 0.55rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink-soft);
    font: inherit;
    font-size: var(--step-0);
    font-weight: 600;
    cursor: pointer;
  }

  .crumb:hover,
  .crumb[aria-expanded='true'] {
    background: var(--accent-wash);
    color: var(--ink);
  }

  .crumb.home {
    margin-left: -0.55rem;
  }

  .crumb[aria-current='page'],
  .crumb.course {
    color: var(--ink);
  }

  .crumb .name {
    min-width: 0;
    max-width: 18rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mark {
    flex: none;
  }

  .sep {
    color: var(--pencil);
  }

  .course {
    font-size: var(--step-0);
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .switch {
    position: relative;
    min-width: 0;
  }

  .course-menu {
    animation: enter-drop var(--quick) var(--ease-out);
    position: absolute;
    top: calc(100% + 0.35rem);
    left: 0;
    z-index: 50;
    display: grid;
    min-width: 18rem;
    max-width: 26rem;
    max-height: 60vh;
    margin: 0;
    padding: 0.35rem;
    overflow-y: auto;
    list-style: none;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: var(--shadow);
  }

  .course-menu button {
    display: grid;
    gap: 0.1rem;
    width: 100%;
    padding: 0.45rem 0.6rem;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .course-menu button:hover,
  .course-menu button:focus-visible {
    background: var(--accent-wash);
  }

  .course-menu button.active .title::after {
    content: ' ✓';
    color: var(--accent);
  }

  .course-menu .title {
    font-weight: 600;
  }

  .course-menu .meta {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .course-menu .all {
    margin-top: 0.25rem;
    padding-top: 0.25rem;
    border-top: 1px solid var(--rule);
  }

  /* One quiet switch for the course's three places: the open one is lifted onto a sheet rather than filled with ink. */
  .places {
    grid-column: 2;
    display: flex;
    gap: 2px;
    padding: 3px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--rule) 55%, transparent);
  }

  .place {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2rem;
    padding: 0.25rem 0.9rem;
    border: 0;
    border-radius: 999px;
    background: transparent;
    /* The same text as the side panel's switcher on the right, so the bar's two switches read alike. */
    color: var(--accent);
    font: inherit;
    font-size: var(--step-0);
    font-weight: 500;
    line-height: 1.2;
    cursor: pointer;
    transition:
      color var(--quick) ease,
      background-color var(--quick) ease,
      box-shadow var(--quick) ease;
  }

  .place:hover {
    background: var(--accent-wash);
  }

  .place[aria-current='page'] {
    /* In the dark, the raised sheet is darker than the track, so the lift is a lighter fill there. */
    background: light-dark(var(--raised), var(--rule-strong));
    font-weight: 600;
    box-shadow: 0 1px 2px var(--shadow-near), 0 0 0 1px color-mix(in srgb, var(--rule) 60%, transparent);
  }

  .dot {
    flex: none;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 999px;
    background: var(--marker);
  }

  .actions {
    grid-column: 3;
    justify-self: end;
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  /* One control for the side panel's three views, so it reads as a single switch rather than three more buttons. */
  .switcher {
    display: flex;
    gap: 2px;
    margin-inline: 0.6rem 0.35rem;
    padding: 2px;
    border: 1px solid color-mix(in srgb, var(--rule) 70%, transparent);
    border-radius: 999px;
    transition: border-color var(--quick) ease, background-color var(--quick) ease;
  }

  .switcher.open {
    border-color: var(--rule);
    background: var(--raised);
  }

  .switcher .btn {
    min-height: 2rem;
    border-radius: 999px;
  }

  .count {
    min-width: 1.25rem;
    padding: 0 0.35rem;
    border-radius: 999px;
    background: var(--marker);
    color: #2a2208;
    font-size: 0.75rem;
    line-height: 1.25rem;
    font-weight: 600;
  }

  .icon {
    padding-inline: 0.5rem;
  }

  .update {
    animation: enter-fade var(--settle) ease;
    gap: 0.3rem;
    border-radius: 999px;
    border-color: transparent;
    background: var(--accent-wash);
    color: var(--accent);
    font-weight: 600;
  }

  .update:hover {
    background: var(--accent);
    color: var(--on-accent);
  }

  .studio-status {
    animation: enter-fade var(--settle) ease;
    gap: 0.4rem;
    border-radius: 999px;
    border-color: var(--rule);
    background: var(--raised);
    color: var(--ink-soft);
  }

  .studio-status.needs {
    border-color: var(--caution);
    background: var(--caution-wash);
    color: var(--caution);
    font-weight: 600;
  }

  .pulse {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: currentColor;
    animation: studio-pulse 1.2s ease-in-out infinite;
  }

  .studio-status:not(.needs) .pulse {
    background: var(--accent);
  }

  @keyframes studio-pulse {
    50% {
      opacity: 0.3;
    }
  }

  @media (hover: none), (max-width: 30rem) {
    .shortcuts {
      display: none;
    }
  }

  .narrow-only {
    display: none;
  }

  @media (max-width: 56rem) {
    .menu,
    .narrow-only {
      display: inline-flex;
    }

    .wide-only {
      display: none;
    }

    .shortcuts {
      display: none;
    }

    .topbar {
      gap: 0.5rem;
    }
  }

  /* A title cut to a letter or two says nothing; the section heading below names where you are. */
  @media (max-width: 30rem) {
    .course {
      display: none;
    }

    /* On a phone the course switcher keeps only its arrow, and the three places tighten, so nothing scrolls sideways. */
    .sep,
    .crumb.course .name {
      display: none;
    }

    .place {
      padding: 0.25rem 0.5rem;
    }

    .topbar {
      gap: 0.5rem;
    }
  }

  /* Connecting and reconnecting come and go with the host; they fade rather than blink. */
  .actions > [role='status'] {
    animation: enter-fade var(--settle) ease;
  }
</style>
