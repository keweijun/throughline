<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { LauncherStatus } from '../lib/types';

  /**
   * Where the launcher is, in this platform's words, and the two places worth keeping it (ADR 0017): the desktop, and
   * the Dock or taskbar. Throughline adds itself to macOS's Dock and GNOME's dock; Windows lets no program pin itself
   * to the taskbar, so there the card shows the four clicks it takes.
   */
  let { launcher }: { launcher: LauncherStatus } = $props();

  let busy = $state<'desktop' | 'dock' | null>(null);
  let onDesktop = $state(false);
  let addedToDock = $state(false);
  const docked = $derived(addedToDock || !!launcher.docked);

  const where = $derived(
    {
      nt: t('Throughline is in the Start menu: search for “Throughline”.'),
      darwin: t('Throughline is in your Applications folder: open it from Launchpad or Spotlight.'),
      'darwin-home': t('Throughline is in Applications in your home folder: open it from Launchpad or Spotlight.'),
      linux: t('Throughline is in your app menu.'),
    }[launcher.platform],
  );
  const mac = $derived(launcher.platform === 'darwin' || launcher.platform === 'darwin-home');

  // Success shows on the tile; a failure goes to the shared error banner.
  async function run(action: 'desktop' | 'dock') {
    busy = action;
    try {
      await api.post(`/api/launcher/${action}`);
      if (action === 'desktop') onDesktop = true;
      else addedToDock = true;
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    }
    busy = null;
  }
</script>

{#snippet tick()}
  <svg class="tick" viewBox="0 0 16 16" aria-hidden="true"><path d="M3.8 8.4 6.6 11.2 12.2 5" /></svg>
{/snippet}

{#if launcher.exists}
  <p class="where">{where}</p>
  <div class="ways">
    <section class="way" aria-label={t('Desktop')}>
      <span class="icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M9 20h6M12 16.5V20" /></svg>
      </span>
      <h4>{t('Desktop')}</h4>
      <p>{t('A shortcut on your desktop.')}</p>
      {#if onDesktop}
        <span class="done" role="status">{@render tick()}{t('Added to your desktop.')}</span>
      {:else}
        <button class="btn btn-small" disabled={busy !== null} onclick={() => run('desktop')}>{t('Add to desktop')}</button>
      {/if}
    </section>

    <section class="way" aria-label={launcher.platform === 'nt' ? t('Taskbar') : t('Dock')}>
      <span class="icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><rect x="2.5" y="14" width="19" height="6" rx="2" /><rect x="6" y="16" width="2.5" height="2" rx=".5" /><rect x="10.75" y="16" width="2.5" height="2" rx=".5" /><rect x="15.5" y="16" width="2.5" height="2" rx=".5" /><path d="M12 4v7M9 8l3 3 3-3" /></svg>
      </span>
      {#if launcher.platform === 'nt'}
        <h4>{t('Taskbar')}</h4>
        <p>{t('Windows asks you to pin apps yourself:')}</p>
        <ol class="clicks">
          <li><span><kbd>⊞</kbd> {t('Start')}</span></li>
          <li><span>{t('Type “Throughline”')}</span></li>
          <li><span>{t('Right-click it')}</span></li>
          <li><span>{t('Pin to taskbar')}</span></li>
        </ol>
      {:else if launcher.dock}
        <h4>{t('Dock')}</h4>
        <p>{mac ? t('Always in the Dock, one click away.') : t('Always in your dock, one click away.')}</p>
        {#if docked}
          <span class="done" role="status">{@render tick()}{mac ? t('In the Dock.') : t('In your dock.')}</span>
        {:else}
          <button class="btn btn-small" disabled={busy !== null} onclick={() => run('dock')}>{mac ? t('Add to Dock') : t('Add to dock')}</button>
        {/if}
      {:else}
        <h4>{t('Dock')}</h4>
        <p>{t('Right-click Throughline in your app menu and add it to your dock, panel or favourites.')}</p>
      {/if}
    </section>
  </div>
{:else}
  <p class="where">{t('This computer has no Throughline launcher yet. To add one, run this in a terminal:')} <code>throughline setup</code></p>
{/if}

<style>
  .where {
    color: var(--ink-soft);
    font-size: var(--step--1);
  }

  .ways {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.7rem;
    margin-top: 0.7rem;
  }

  .way {
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-rows: auto 1fr auto;
    column-gap: 0.75rem;
    row-gap: 0.2rem;
    padding: 0.85rem 0.95rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--raised);
  }

  .icon {
    grid-row: span 3;
    display: grid;
    place-items: center;
    width: 2.3rem;
    height: 2.3rem;
    border-radius: 8px;
    background: var(--accent-wash);
  }
  .icon svg {
    width: 1.25rem;
    height: 1.25rem;
    fill: none;
    stroke: var(--accent);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  h4 {
    font: 600 var(--step-0) / 1.3 var(--sans);
  }
  .way p {
    font-size: var(--step--1);
    line-height: 1.45;
    color: var(--pencil);
  }
  .way .btn,
  .done {
    justify-self: start;
    margin-top: 0.45rem;
  }

  .done {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    color: var(--good);
    font-size: var(--step--1);
    font-weight: 600;
  }
  .tick {
    width: 0.95rem;
    height: 0.95rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  /* The clicks Windows asks for, numbered, two to a row. */
  .clicks {
    display: grid;
    grid-template-columns: auto auto;
    justify-content: start;
    gap: 0.35rem 1rem;
    margin: 0.5rem 0 0;
    padding: 0;
    list-style: none;
    counter-reset: click;
    font-size: var(--step--1);
  }
  .clicks li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    white-space: nowrap;
  }
  .clicks li::before {
    counter-increment: click;
    content: counter(click);
    display: grid;
    place-items: center;
    width: 1.15rem;
    height: 1.15rem;
    border-radius: 50%;
    background: var(--accent-wash);
    color: var(--accent);
    font-size: 0.68rem;
    font-weight: 600;
  }
  .clicks li:last-child span {
    font-weight: 600;
    color: var(--accent);
  }
  .clicks kbd {
    font: inherit;
  }
</style>
