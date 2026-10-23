<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app, type PanelTab } from '../lib/store.svelte';

  const route = $derived(app.state?.curriculum.route ?? []);
  const index = $derived(app.routeIndex(app.currentId));
  const studying = $derived(!!app.state && !app.libraryOpen);
  const openQuestions = $derived(
    (app.state?.questions ?? []).filter((q) => q.status === 'unanswered' || q.status === 'suggested' || (q.choice === 'accept' && !q.returned)).length,
  );

  // Each side-panel tab has its own toggle, mirroring the tabs inside the panel.
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
    <div class="progress" title={t("Your position on the course route")}>
      <span>{t('Section {number} of {total}', { number: index + 1, total: route.length })}</span>
      <span class="track" aria-hidden="true"><span style:width="{((index + 1) / route.length) * 100}%"></span></span>
    </div>
  {/if}

  <div class="actions">
    {#if app.connection !== 'live'}
      <span class="chip chip-caution" role="status">
        {app.connection === 'connecting' ? t("Connecting…") : t("Reconnecting · your work is saved")}
      </span>
    {/if}
    <button class="btn btn-quiet" aria-pressed={app.libraryOpen} disabled={app.libraryOpen && !app.state} aria-label={t("Courses")} onclick={() => (app.libraryOpen ? (app.libraryOpen = false) : app.showLibrary())}>
      <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 3.5h3v13H4zM8.5 3.5h3v13h-3zM13 4.2l2.8-.8 2.2 12.6-2.8.6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
      <span class="wide-only">{t("Courses")}</span>
    </button>
    <button class="btn btn-quiet" disabled={!studying} aria-pressed={showing('questions')} onclick={() => toggle('questions')}>
      {t("Questions")}{#if openQuestions}<span class="count">{openQuestions}</span>{/if}
    </button>
    <button class="btn btn-quiet" disabled={!studying} aria-pressed={showing('source')} aria-label={t("Source")} title={t("Source reader (s)")} onclick={() => toggle('source')}>
      <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 4.5c2.5-1 5-1 7 .5v11c-2-1.5-4.5-1.5-7-.5zM17 4.5c-2.5-1-5-1-7 .5v11c2-1.5 4.5-1.5 7-.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
      <span class="wide-only">{t("Source")}</span>
    </button>
    <button class="btn btn-quiet" disabled={!studying} aria-pressed={showing('notes')} aria-label={t("Notes")} onclick={() => toggle('notes')}>
      <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M13.5 3.5l3 3-9 9H4.5v-3zM11.5 5.5l3 3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
      <span class="wide-only">{t("Notes")}</span>
    </button>
    <button class="btn btn-quiet icon" onclick={() => (app.settingsOpen = true)} aria-label={t("Settings")} title={t("Settings: language, appearance and teacher")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="10" cy="10" r="2.6" fill="none" stroke="currentColor" stroke-width="1.5" /><path d="M10 2.5v2.2M10 15.3v2.2M2.5 10h2.2M15.3 10h2.2M4.7 4.7l1.6 1.6M13.7 13.7l1.6 1.6M4.7 15.3l1.6-1.6M13.7 6.3l1.6-1.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" /></svg>
    </button>
    <button class="btn btn-quiet icon shortcuts" onclick={() => (app.shortcutsOpen = true)} aria-label={t("Keyboard shortcuts")} title={t("Keyboard shortcuts (?)")}>?</button>
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

  .shortcuts {
    font-weight: 600;
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
  }
</style>
