<script lang="ts">
  import { app } from '../lib/store.svelte';

  let dialog: HTMLDialogElement | undefined = $state();

  $effect(() => {
    if (!dialog) return;
    if (app.shortcutsOpen && !dialog.open) dialog.showModal();
    else if (!app.shortcutsOpen && dialog.open) dialog.close();
  });

  const keys: [string, string][] = [
    ['/', 'Ask a side question'],
    ['[', 'Previous section'],
    [']', 'Next section'],
    ['s', 'Show or hide the source reader'],
    ['Esc', 'Close a drawer or popup'],
    ['?', 'Show these shortcuts'],
  ];
</script>

<dialog bind:this={dialog} onclose={() => (app.shortcutsOpen = false)} aria-labelledby="shortcuts-title">
  <h2 id="shortcuts-title">Keyboard shortcuts</h2>
  <dl>
    {#each keys as [key, action]}
      <div><dt><kbd>{key}</kbd></dt><dd>{action}</dd></div>
    {/each}
  </dl>
  <button class="btn btn-small" onclick={() => (app.shortcutsOpen = false)}>Done</button>
</dialog>

<style>
  dialog {
    width: min(22rem, calc(100vw - 2rem));
    padding: 1.25rem 1.4rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.35);
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
    margin-bottom: 0.75rem;
  }

  dl {
    display: grid;
    gap: 0.45rem;
    margin: 0 0 1rem;
  }

  dl div {
    display: grid;
    grid-template-columns: 3rem 1fr;
    align-items: center;
    font-size: var(--step-0);
  }

  dd {
    margin: 0;
  }

  kbd {
    display: inline-block;
    min-width: 1.6rem;
    padding: 0.05rem 0.4rem;
    border: 1px solid var(--rule-strong);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: var(--raised);
    font-family: var(--mono);
    font-size: 0.8rem;
    text-align: center;
  }
</style>
