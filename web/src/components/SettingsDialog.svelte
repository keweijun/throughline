<script lang="ts">
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import type { Provider, Settings } from '../lib/types';

  type Draft = Provider & { api_key?: string; isNew: boolean };

  const presets: { name: string; draft: Partial<Draft> }[] = [
    { name: 'OpenAI', draft: { id: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1', api_key_env: 'OPENAI_API_KEY' } },
    { name: 'OpenRouter', draft: { id: 'openrouter', label: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1', api_key_env: 'OPENROUTER_API_KEY' } },
    { name: 'Ollama', draft: { id: 'ollama', label: 'Ollama', base_url: 'http://127.0.0.1:11434/v1' } },
    { name: 'LM Studio', draft: { id: 'lm-studio', label: 'LM Studio', base_url: 'http://127.0.0.1:1234/v1' } },
    { name: 'Other', draft: { id: 'custom', label: 'Custom provider', base_url: 'https://' } },
  ];

  let dialog: HTMLDialogElement | undefined = $state();
  let draft = $state<Draft | null>(null);
  let models = $state<string[]>([]);
  let modelMessage = $state('');
  let message = $state('');
  let busy = $state(false);

  const settings = $derived(app.state?.settings);

  $effect(() => {
    if (!dialog) return;
    if (app.settingsOpen && !dialog.open) {
      draft = null;
      message = '';
      dialog.showModal();
    } else if (!app.settingsOpen && dialog.open) dialog.close();
  });

  async function save(fn: () => Promise<Settings>, done: string) {
    busy = true;
    message = '';
    const result = await app.act(fn);
    busy = false;
    if (result) {
      message = done;
      draft = null;
    }
  }

  function activate(provider: Provider) {
    return save(() => api.post<Settings>('/api/settings/active', { id: provider.id }), `Using ${provider.label} for new requests.`);
  }

  function edit(provider: Provider) {
    draft = { ...provider, api_key: '', isNew: false };
    models = [];
    modelMessage = '';
  }

  function add(preset: Partial<Draft>) {
    const taken = new Set(settings?.providers.map((p) => p.id));
    let id = preset.id!;
    for (let n = 2; taken.has(id); n++) id = `${preset.id}-${n}`;
    draft = { kind: 'openai', model: '', effort: '', api_key: '', api_key_env: '', ...preset, id, isNew: true } as Draft;
    models = [];
    modelMessage = '';
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    if (!draft) return;
    const { isNew, has_api_key, api_key, ...provider } = draft;
    const body = api_key ? { ...provider, api_key } : provider;
    void save(() => api.put<Settings>('/api/settings/providers', body), `Saved ${draft.label}.`);
  }

  function remove(provider: Provider) {
    return save(() => api.delete<Settings>(`/api/settings/providers/${encodeURIComponent(provider.id)}`), `Removed ${provider.label}.`);
  }

  async function loadModels() {
    if (!draft) return;
    modelMessage = 'Loading models…';
    try {
      const { isNew, has_api_key, ...provider } = draft;
      const result = await api.post<{ models: string[] }>('/api/settings/models', provider.api_key ? provider : { ...provider, api_key: undefined });
      models = result.models;
      modelMessage = models.length ? `${models.length} models available.` : 'The provider listed no models. Type the model name instead.';
    } catch (e) {
      modelMessage = (e as Error).message;
    }
  }
</script>

<dialog bind:this={dialog} onclose={() => (app.settingsOpen = false)} aria-labelledby="settings-title">
  <header>
    <h2 id="settings-title">Model settings</h2>
    <button class="btn btn-quiet btn-small" onclick={() => (app.settingsOpen = false)}>Close</button>
  </header>

  {#if settings}
    {#if !draft}
      <p class="intro">Choose who teaches. New lessons, answers and feedback use this model; text already written stays as it is.</p>
      <ul class="providers">
        {#each settings.providers as provider (provider.id)}
          {@const active = provider.id === settings.active}
          <li class:active>
            <div class="info">
              <p class="name">{provider.label} {#if active}<span class="chip">In use</span>{/if}</p>
              <p class="detail">
                {provider.kind === 'codex' ? 'Codex CLI on this computer' : provider.base_url}
                · {(active ? settings.active_model : provider.model) || 'default model'}
              </p>
              {#if provider.kind === 'openai' && !provider.has_api_key}
                <p class="detail warn">No API key set{provider.api_key_env ? ` (looked for ${provider.api_key_env})` : ''}.</p>
              {/if}
            </div>
            <div class="row">
              {#if !active}<button class="btn btn-small" disabled={busy} onclick={() => activate(provider)}>Use</button>{/if}
              <button class="btn btn-quiet btn-small" onclick={() => edit(provider)}>Edit</button>
              {#if !active}
                <button class="btn btn-quiet btn-small" disabled={busy} onclick={() => remove(provider)}>Remove</button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>

      <h3>Add an OpenAI-compatible provider</h3>
      <div class="presets">
        {#each presets as preset}
          <button class="btn btn-small" onclick={() => add(preset.draft)}>{preset.name}</button>
        {/each}
      </div>

      {#if settings.overridden}
        <p class="note">This host was started with a provider or model on the command line. Choosing a provider here replaces it.</p>
      {/if}
      <p class="note">Saved for your user account in <code>{settings.path}</code>, never inside a course folder.</p>
    {:else}
      <form class="edit" onsubmit={submit}>
        <h3>{draft.isNew ? 'New provider' : `Edit ${draft.label}`}</h3>
        <label class="field"><span>Name</span><input type="text" bind:value={draft.label} required /></label>
        {#if draft.isNew}
          <label class="field"><span>ID</span><input type="text" bind:value={draft.id} pattern="[a-z0-9][a-z0-9-]*" required /></label>
        {/if}
        {#if draft.kind === 'openai'}
          <label class="field">
            <span>Base URL</span>
            <input type="url" bind:value={draft.base_url} required placeholder="https://api.example.com/v1" />
          </label>
        {/if}
        <label class="field">
          <span>Model</span>
          <input type="text" bind:value={draft.model} list="model-options" placeholder={draft.kind === 'codex' ? 'Leave empty for your Codex default' : 'For example: gpt-5.1'} required={draft.kind === 'openai'} />
          <datalist id="model-options">
            {#each models as model}<option value={model}></option>{/each}
          </datalist>
        </label>
        {#if draft.kind === 'openai'}
          <div class="row">
            <button type="button" class="btn btn-quiet btn-small" onclick={loadModels}>Load available models</button>
            {#if modelMessage}<span class="detail">{modelMessage}</span>{/if}
          </div>
          <label class="field">
            <span>API key</span>
            <input type="password" bind:value={draft.api_key} autocomplete="off" placeholder={draft.has_api_key ? 'A key is saved. Leave empty to keep it.' : 'Optional for local servers'} />
          </label>
          <label class="field">
            <span>Or read the key from an environment variable</span>
            <input type="text" bind:value={draft.api_key_env} placeholder="OPENAI_API_KEY" />
          </label>
        {/if}
        <label class="field">
          <span>Reasoning effort</span>
          <select bind:value={draft.effort}>
            <option value="">{draft.kind === 'codex' ? 'Medium' : 'Provider default'}</option>
            <option value="minimal">Minimal</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>
        <div class="row">
          <button class="btn btn-primary" type="submit" disabled={busy}>Save provider</button>
          <button class="btn btn-quiet" type="button" onclick={() => (draft = null)}>Cancel</button>
        </div>
      </form>
    {/if}
    {#if message}<p class="message" role="status">{message}</p>{/if}
  {/if}
</dialog>

<style>
  dialog {
    width: min(36rem, calc(100vw - 2rem));
    max-height: calc(100vh - 4rem);
    padding: 1.25rem 1.5rem 1.5rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.45);
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  h3 {
    margin: 1.5rem 0 0.6rem;
    font-size: var(--step-0);
    font-weight: 600;
  }

  .edit h3 {
    margin-top: 0;
  }

  .intro,
  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .note {
    margin-top: 1rem;
    overflow-wrap: anywhere;
  }

  .providers {
    display: grid;
    gap: 0.5rem;
    margin: 1rem 0 0;
    padding: 0;
    list-style: none;
  }

  .providers li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.7rem 0.85rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
  }

  .providers li.active {
    border-color: var(--accent);
  }

  .info {
    min-width: 0;
  }

  .name {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
  }

  .detail {
    font-size: var(--step--1);
    color: var(--pencil);
    overflow-wrap: anywhere;
  }

  .warn {
    color: var(--caution);
  }

  .row,
  .presets {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
  }

  .edit {
    display: grid;
    gap: 0.9rem;
  }

  .message {
    margin-top: 1rem;
    font-size: var(--step--1);
    color: var(--good);
  }
</style>
