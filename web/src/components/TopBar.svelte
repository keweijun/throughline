<script lang="ts">
  import { app } from '../lib/store.svelte';

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
  <button
    class="btn btn-quiet menu"
    aria-label="Course contents"
    aria-expanded={app.routeOpen}
    aria-controls="route"
    onclick={() => (app.routeOpen = !app.routeOpen)}
  >
    <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" /></svg>
  </button>

  <div class="title">
    <svg class="mark" viewBox="0 0 32 32" width="26" height="26" aria-hidden="true"><rect width="32" height="32" rx="7" fill="var(--accent)" /><path d="M9 22.5V9.5h5.2c3.3 0 5.3 1.7 5.3 4.4 0 2.8-2 4.5-5.3 4.5H12.2" fill="none" stroke="var(--sheet)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" /><path d="M17.5 22.5h5.5" stroke="var(--marker)" stroke-width="2.6" stroke-linecap="round" /></svg>
    <span class="course">{app.state?.course.title ?? 'Guided Learning'}</span>
  </div>

  {#if route.length && index >= 0}
    <div class="progress" title="Your position on the course route">
      <span>Section {index + 1} of {route.length}</span>
      <span class="track" aria-hidden="true"><span style:width="{((index + 1) / route.length) * 100}%"></span></span>
    </div>
  {/if}

  <div class="actions">
    {#if app.connection !== 'live'}
      <span class="chip chip-caution" role="status">
        {app.connection === 'connecting' ? 'Connecting…' : 'Reconnecting · your work is saved'}
      </span>
    {/if}
    <button class="btn btn-quiet model" onclick={() => (app.settingsOpen = true)} title="Teacher settings">
      <span class="model-name">Codex · {app.state?.settings.model || 'default model'}</span>
    </button>
    <button
      class="btn btn-quiet"
      aria-pressed={app.panelOpen && app.panelTab === 'questions'}
      onclick={() => (app.panelOpen && app.panelTab === 'questions' ? (app.panelOpen = false) : app.openPanel('questions'))}
    >
      Questions{#if openQuestions}<span class="count">{openQuestions}</span>{/if}
    </button>
    <button class="btn btn-quiet icon shortcuts" onclick={() => (app.shortcutsOpen = true)} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)">?</button>
    <button class="btn btn-quiet icon" onclick={toggleTheme} aria-label="Switch light or dark theme">
      <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 3a7 7 0 1 0 0 14V3Z" fill="currentColor" /><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="1.5" /></svg>
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

  @media (max-width: 56rem) {
    .menu {
      display: inline-flex;
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
