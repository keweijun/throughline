<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type PanelTab } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';

  const route = $derived(app.state?.curriculum.route ?? []);
  const index = $derived(app.routeIndex(app.currentId));
  // The bar fills as sections are studied to the end, so starting the last section does not read as finishing the course.
  const studied = $derived(route.filter((id) => app.studied(id)).length);
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

  <div class="title">
    <svg class="mark" viewBox="0 0 32 32" width="26" height="26" aria-hidden="true"><rect width="32" height="32" rx="7.5" fill="#24366e" /><path d="M6.5 9.2c3.4-1.5 6.6-1.5 9 0v15.6c-2.4-1.5-5.6-1.5-9 0z" fill="#fbfcfd" opacity=".78" /><path d="M16.5 9.2c2.4-1.5 5.6-1.5 9 0v15.6c-3.4-1.5-6.6-1.5-9 0z" fill="#fbfcfd" /><path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#24366e" stroke-width="4.6" stroke-linecap="round" /><path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#f0d25c" stroke-width="2.5" stroke-linecap="round" /></svg>
    <span class="course">{studying ? app.state!.course.title : t("Throughline")}</span>
  </div>

  {#if route.length && index >= 0 && studying}
    <div class="progress" title={t("{studied} of {total} sections studied", { studied, total: route.length })}>
      <span>{t('Section {number} of {total}', { number: index + 1, total: route.length })}</span>
      <span class="track" aria-hidden="true"><span style:width="{(studied / route.length) * 100}%"></span></span>
    </div>
  {/if}

  <div class="actions">
    {#if app.connection !== 'live'}
      <span class="chip chip-caution" role="status">
        {app.connection === 'connecting' ? t("Connecting…") : t("Reconnecting · your work is saved")}
      </span>
    {/if}
    <!-- Before a course is open the library is the only page, so Courses just shows it is where you are. -->
    <button class="btn btn-quiet" aria-pressed={app.libraryOpen} aria-label={t("Courses")} onclick={() => (app.libraryOpen ? app.state && (app.libraryOpen = false) : app.showLibrary())}>
      <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 3.5h3v13H4zM8.5 3.5h3v13h-3zM13 4.2l2.8-.8 2.2 12.6-2.8.6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
      <span class="wide-only">{t("Courses")}</span>
    </button>
    {#if studying && review}
      <button
        id="open-review"
        class="btn btn-quiet review"
        aria-pressed={app.reviewOpen}
        aria-label={t("Review")}
        title={t("Answer questions from memory on what you have studied")}
        onclick={() => (app.reviewOpen ? (app.reviewOpen = false) : app.showReview())}
      >
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M15.5 10a5.5 5.5 0 1 1-1.6-3.9M14.5 3v3.4h-3.4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Review")}</span>
      </button>
    {/if}
    {#if studying}
      <div class="switcher" class:open={app.panelOpen} role="group" aria-label={t("Questions and sources")}>
      <button id="toggle-questions" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('questions')} onclick={() => toggle('questions')}>
        {t("Questions")}{#if openQuestions}<span class="count">{openQuestions}</span>{/if}
      </button>
      <button id="toggle-source" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('source')} aria-label={t("Source")} title={t("Source reader (s)")} onclick={() => toggle('source')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 4.5c2.5-1 5-1 7 .5v11c-2-1.5-4.5-1.5-7-.5zM17 4.5c-2.5-1-5-1-7 .5v11c2-1.5 4.5-1.5 7-.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Source")}</span>
      </button>
      <button id="toggle-notes" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('notes')} aria-label={t("Notes")} onclick={() => toggle('notes')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M13.5 3.5l3 3-9 9H4.5v-3zM11.5 5.5l3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Notes")}</span>
      </button>
      <button id="toggle-memory" class="btn btn-quiet" aria-controls="auxiliary" aria-pressed={showing('memory')} aria-label={t("Memory")} title={t("What the teacher remembers about this course")} onclick={() => toggle('memory')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 3.5a5 5 0 0 0-3 9v2.5h6V12.5a5 5 0 0 0-3-9zM8 17h4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Memory")}</span>{#if suggested}<span class="count">{suggested}</span>{/if}
      </button>
      <button id="toggle-studio" class="btn btn-quiet studio-toggle" aria-controls="auxiliary" aria-pressed={showing('studio')} aria-label={t("Studio")} title={t("Studio: create and change courses with Codex (d)")} onclick={() => toggle('studio')}>
        <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 2.5l1.6 4.4 4.4 1.6-4.4 1.6L10 14.5l-1.6-4.4L4 8.5l4.4-1.6zM15.5 13l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" /></svg>
        <span class="wide-only">{t("Studio")}</span>
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
    {#if app.update?.available}
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
    <button class="btn btn-quiet icon" onclick={() => (app.settingsOpen = true)} aria-label={t("Settings")} title={t("Settings: course, teacher, appearance and about")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M16.02 8.14L18.08 8.61L18.08 11.39L16.02 11.86L15.57 12.94L16.70 14.73L14.73 16.70L12.94 15.57L11.86 16.02L11.39 18.08L8.61 18.08L8.14 16.02L7.06 15.57L5.27 16.70L3.30 14.73L4.43 12.94L3.98 11.86L1.92 11.39L1.92 8.61L3.98 8.14L4.43 7.06L3.30 5.27L5.27 3.30L7.06 4.43L8.14 3.98L8.61 1.92L11.39 1.92L11.86 3.98L12.94 4.43L14.73 3.30L16.70 5.27L15.57 7.06Z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" /><circle cx="10" cy="10" r="2.5" fill="none" stroke="currentColor" stroke-width="1.4" /></svg>
    </button>
    <button class="btn btn-quiet icon shortcuts" onclick={() => (app.shortcutsOpen = true)} aria-label={t("Keyboard shortcuts")} title={t("Keyboard shortcuts (?)")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><rect x="1.75" y="4.5" width="16.5" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.4" /><path d="M5 8h.01M8 8h.01M11 8h.01M14.5 8h.5M6.5 10.5h.01M9.5 10.5h.01M12.5 10.5h.01M6.5 13h7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
    </button>
  </div>
</header>

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: 40;
    display: flex;
    align-items: center;
    gap: 1.25rem;
    height: var(--topbar);
    padding: 0 clamp(0.75rem, 2vw, 1.5rem);
    background: color-mix(in srgb, var(--ground) 88%, transparent);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--rule);
  }

  .menu {
    display: none;
  }

  .title {
    display: flex;
    flex: 0 1 auto;
    align-items: center;
    gap: 0.65rem;
    min-width: 0;
  }

  .mark {
    flex: none;
  }

  .course {
    font-size: var(--step-0);
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .progress {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: var(--step--1);
    color: var(--pencil);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .track {
    width: 7rem;
    height: 4px;
    border-radius: 2px;
    background: var(--rule);
    overflow: hidden;
  }

  .track span {
    transition: width 0.4s var(--ease-out);
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .actions {
    display: flex;
    flex: none;
    align-items: center;
    gap: 0.25rem;
    margin-left: auto;
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

  @media (max-width: 68rem) {
    .progress .track {
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

    .progress,
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

    /* Phones have no room for Review beside the panel switcher; it was shown there only when something was due.
       Studio is reached there from the course's own hand-offs (Add files in Studio, …). */
    .review,
    .studio-toggle {
      display: none;
    }
  }
</style>
