<script lang="ts">
  import { api } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import type { LauncherStatus } from '../lib/types';

  /** Where the launcher is, in this platform's words, with Add to desktop and Show launcher (ADR 0017). */
  let { launcher }: { launcher: LauncherStatus } = $props();

  let busy = $state<'desktop' | 'show' | null>(null);
  let done = $state('');

  const where = $derived(
    {
      nt: t('Throughline is in the Start menu: search for “Throughline”. From its folder you can pin it to Start or the taskbar.'),
      darwin: t('Throughline is in your Applications folder: open it from Launchpad or Spotlight. In Finder you can drag it to the Dock.'),
      'darwin-home': t('Throughline is in Applications in your home folder: open it from Launchpad or Spotlight. In Finder you can drag it to the Dock.'),
      linux: t('Throughline is in your app menu. From its folder you can add it to your dock or panel.'),
    }[launcher.platform],
  );
  const shown = $derived(
    launcher.platform === 'nt' ? t('Shown in File Explorer.') : launcher.platform === 'linux' ? t('Opened its folder.') : t('Shown in Finder.'),
  );

  // Success shows beside the buttons; a failure goes to the shared error banner.
  async function run(action: 'desktop' | 'show') {
    busy = action;
    done = '';
    try {
      await api.post(`/api/launcher/${action}`);
      done = action === 'desktop' ? t('Added to your desktop.') : shown;
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    }
    busy = null;
  }
</script>

{#if launcher.exists}
  <p class="where">{where}</p>
  <div class="actions">
    <button class="btn btn-small" disabled={busy !== null} onclick={() => run('desktop')}>{t('Add to desktop')}</button>
    <button class="btn btn-small" disabled={busy !== null} onclick={() => run('show')}>{t('Show launcher')}</button>
    {#if done}<span class="done" role="status">{done}</span>{/if}
  </div>
{:else}
  <p class="where">{t('This computer has no Throughline launcher yet. To add one, run this in a terminal:')} <code>guided-learning setup</code></p>
{/if}

<style>
  .where {
    color: var(--ink-soft);
    font-size: var(--step--1);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.6rem;
  }

  .done {
    color: var(--good);
    font-size: var(--step--1);
  }
</style>
