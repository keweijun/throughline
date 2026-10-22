<script lang="ts">
  import { t, locale, type Language } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';

  let savingLanguage = $state(false);
  async function changeLanguage(event: Event) {
    const select = event.currentTarget as HTMLSelectElement;
    savingLanguage = true;
    await app.setLanguage(select.value as Language);
    select.value = locale.language;
    savingLanguage = false;
  }

  const route = $derived(app.state?.curriculum.route ?? []);
  const index = $derived(app.routeIndex(app.currentId));
  const openQuestions = $derived(
    (app.state?.questions ?? []).filter((q) => q.status === 'unanswered' || q.status === 'suggested' || (q.choice === 'accept' && !q.returned)).length,
  );

  function toggleTheme() {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    try {
      localStorage.setItem('theme', root.dataset.theme);
    } catch {
      // The choice still applies for this visit.
    }
  }
</script>

<header class="topbar">
  {#if app.state && !app.libraryOpen}
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
    <span class="course">{app.libraryOpen || !app.state ? t("Throughline") : app.state.course.title}</span>
  </div>

  {#if route.length && index >= 0 && !app.libraryOpen}
    <div class="progress" title={t("Your position on the course route")}>
      <span>{t('Section {number} of {total}', { number: index + 1, total: route.length })}</span>
      <span class="track" aria-hidden="true"><span style:width="{((index + 1) / route.length) * 100}%"></span></span>
    </div>
  {/if}

  <div class="actions">
    <label class="language" title={t('Language applies to the interface and new teaching content.')}>
      <span class="visually-hidden">{t('Language')}</span>
      <select aria-label={t('Language')} value={locale.language} onchange={changeLanguage} disabled={savingLanguage}>
        <option value="en">English</option>
        <option value="zh-CN">简体中文</option>
      </select>
    </label>
    {#if app.connection !== 'live'}
      <span class="chip chip-caution" role="status">
        {app.connection === 'connecting' ? t("Connecting…") : t("Reconnecting · your work is saved")}
      </span>
    {/if}
    <button class="btn btn-quiet" aria-pressed={app.libraryOpen} disabled={app.libraryOpen && !app.state} aria-label={t("Courses")} onclick={() => (app.libraryOpen ? (app.libraryOpen = false) : app.showLibrary())}>
      <svg class="narrow-only" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M4 3.5h3v13H4zM8.5 3.5h3v13h-3zM13 4.2l2.8-.8 2.2 12.6-2.8.6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" /></svg>
      <span class="wide-only">{t("Courses")}</span>
    </button>
    <button class="btn btn-quiet model" onclick={() => (app.settingsOpen = true)} title={t("Teacher settings")}>
      <span class="visually-hidden">{t("Teacher settings")}: </span><span class="model-name">Codex · {app.settings?.model || t("default model")}</span>
    </button>
    <button
      class="btn btn-quiet"
      disabled={!app.state || app.libraryOpen}
      aria-pressed={app.panelOpen && app.panelTab === 'questions'}
      onclick={() => (app.panelOpen && app.panelTab === 'questions' ? (app.panelOpen = false) : app.openPanel('questions'))}
    >
      {t("Questions")}{#if openQuestions}<span class="count">{openQuestions}</span>{/if}
    </button>
    <button class="btn btn-quiet icon shortcuts" onclick={() => (app.shortcutsOpen = true)} aria-label={t("Keyboard shortcuts")} title={t("Keyboard shortcuts (?)")}>?</button>
    <button class="btn btn-quiet icon" onclick={toggleTheme} aria-label={t("Switch light or dark theme")}>
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 3a7 7 0 1 0 0 14V3Z" fill="currentColor" /><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1.5" /></svg>
    </button>
  </div>
</header>

<style>
  .language { flex: none; }
  .language select { width: auto; max-width: 7rem; font-size: var(--step--1); padding: 0.35rem; }
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
    align-items: center;
    gap: 0.25rem;
    margin-left: auto;
  }

  .model {
    color: var(--ink-soft);
    max-width: 18rem;
  }

  .model-name {
    overflow: hidden;
    text-overflow: ellipsis;
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

  @media (hover: none) {
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
    .model {
      display: none;
    }

    .topbar {
      gap: 0.5rem;
    }
  }
</style>
