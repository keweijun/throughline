<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';

  /**
   * How Studio runs, chosen where it is used, as in Codex (ADR 0016): its model and reasoning effort, the teacher's
   * until the learner picks Studio's own, and its access. Each opens a small menu above the writing box.
   */
  let open = $state<'model' | 'access' | null>(null);
  let root = $state<HTMLElement>();
  let saving = $state(false);
  let modelsError = $state('');

  const EFFORTS: { id: string; label: MessageKey }[] = [
    { id: 'minimal', label: 'Minimal' },
    { id: 'low', label: 'Low' },
    { id: 'medium', label: 'Medium' },
    { id: 'high', label: 'High' },
    { id: 'xhigh', label: 'Extra high' },
    { id: 'max', label: 'Max' },
  ];

  const teacherModel = $derived(app.settings?.model ?? '');
  const model = $derived(studio.choice.model || teacherModel);
  const effort = $derived(studio.choice.effort || app.settings?.effort || 'medium');
  const entry = (id: string) => studio.models?.find((m) => (id ? m.id === id : m.default));
  const modelName = (id: string) => entry(id)?.name ?? (id || t('Codex default'));
  const efforts = $derived.by(() => {
    const offered = EFFORTS.filter((e) => entry(model)?.efforts?.includes(e.id));
    return offered.length ? offered : EFFORTS;
  });
  const effortLabel = $derived(t(EFFORTS.find((e) => e.id === effort)?.label ?? 'Medium'));

  // The chip names the model, so the list is asked for as soon as Codex can run Studio, not when the menu opens.
  $effect(() => {
    if (studio.available) studio.loadModels().catch(() => {});
  });

  async function toggle(menu: 'model' | 'access') {
    open = open === menu ? null : menu;
    if (open === 'model' && !studio.models) {
      modelsError = '';
      try {
        await studio.loadModels(true);
      } catch (e) {
        modelsError = e instanceof Error ? e.message : String(e);
      }
    }
    // On Windows, whether Codex's sandbox is ready is known only from Codex.
    if (open === 'access') void studio.loadAccess();
  }

  async function save(change: () => Promise<unknown>) {
    saving = true;
    try {
      await change();
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
    }
    saving = false;
  }

  // Picking a model keeps the effort when the model offers it, else the nearest below it.
  function pickModel(id: string) {
    if (!id) return save(() => studio.setChoice({ model: '', effort: '' }));
    const offered = studio.models?.find((m) => m.id === id)?.efforts ?? [];
    const below = EFFORTS.slice(0, EFFORTS.findIndex((e) => e.id === effort)).reverse().find((e) => offered.includes(e.id));
    const kept = !offered.length || offered.includes(effort) ? effort : (below?.id ?? offered[0]);
    return save(() => studio.setChoice({ model: id, effort: kept }));
  }

  function pickAccess(full: boolean) {
    open = null;
    if (full !== studio.access?.full_access) void save(() => studio.setFullAccess(full));
  }

  // A menu closes on a click outside it or on Escape, as menus do.
  $effect(() => {
    if (!open) return;
    const away = (event: Event) => root && !root.contains(event.target as Node) && (open = null);
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      open = null;
    };
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', escape, true);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', escape, true);
    };
  });
</script>

<span class="controls" bind:this={root}>
  <button
    type="button"
    class="chip"
    id="studio-model"
    aria-haspopup="true"
    aria-expanded={open === 'model'}
    title={t("Studio's model and reasoning effort")}
    onclick={() => void toggle('model')}
  >{modelName(model)} · {effortLabel}</button>
  <button
    type="button"
    class="chip"
    id="studio-access"
    class:full={studio.access?.full_access}
    aria-haspopup="true"
    aria-expanded={open === 'access'}
    title={studio.access?.full_access ? t("Codex can change files anywhere and runs commands without asking.") : t("Codex writes only inside your Throughline folder and asks before anything else.")}
    onclick={() => void toggle('access')}
  >{studio.access?.full_access ? t('Full access') : t('Library access')}</button>

  {#if open === 'model'}
    <!-- Effort first: it is switched more often than the model, and stays in view above a long list of models. -->
    <div class="menu" role="group" aria-label={t("Studio's model and reasoning effort")}>
      <p class="label">{t("Reasoning effort")}</p>
      <div class="segmented" role="radiogroup" aria-label={t("Reasoning effort")}>
        {#each efforts as option (option.id)}
          <label>
            <input
              type="radio"
              name="studio-effort"
              checked={effort === option.id}
              disabled={saving}
              onchange={() => void save(() => studio.setChoice({ model: studio.choice.model, effort: option.id }))}
            />{t(option.label)}
          </label>
        {/each}
      </div>
      <p class="note">{t("Applies to Studio from the next message. Lessons keep the teacher's model, set in Settings.")}</p>
      <p class="label">{t("Model")}</p>
      {#if !studio.models}
        <p class="note" role="status">{modelsError ? `${t("Could not load models from Codex:")} ${modelsError}` : t("Loading models from Codex…")}</p>
      {/if}
      <div class="options models" role="radiogroup" aria-label={t("Model")}>
        <label class="option">
          <input type="radio" name="studio-model" checked={!studio.choice.model} disabled={saving} onchange={() => void pickModel('')} />
          <span class="name">{t("Same as the teacher")}</span>
          <span class="meta">{modelName(teacherModel)}</span>
        </label>
        {#each studio.models ?? [] as option (option.id)}
          <label class="option" title={option.description}>
            <input type="radio" name="studio-model" checked={studio.choice.model === option.id} disabled={saving} onchange={() => void pickModel(option.id)} />
            <span class="name">{option.name}</span>
          </label>
        {/each}
      </div>
    </div>
  {:else if open === 'access'}
    <div class="menu" role="group" aria-label={t("Access")}>
      {#if studio.access?.forced}
        <p class="note">{t("Codex's sandbox is not set up on this Windows computer, so Studio runs with full access, as Codex does here.")}</p>
      {/if}
      <div class="options" role="radiogroup" aria-label={t("Access")}>
        <label class="option">
          <input type="radio" name="studio-access" checked={!studio.access?.full_access} disabled={saving || !!studio.access?.forced} onchange={() => pickAccess(false)} />
          <span class="name">{t("Library access")}</span>
          <span class="meta">{t("Codex writes only inside your Throughline folder and asks before anything else.")}</span>
        </label>
        <label class="option">
          <input type="radio" name="studio-access" checked={!!studio.access?.full_access} disabled={saving || !!studio.access?.forced} onchange={() => pickAccess(true)} />
          <span class="name">{t("Full access")}</span>
          <span class="meta">{t("Codex can change files anywhere and runs commands without asking.")}</span>
        </label>
      </div>
    </div>
  {/if}
</span>

<style>
  /* The chips shorten before the row would wrap, so the box never grows a line while Codex starts or stops. */
  .controls {
    position: relative;
    display: inline-flex;
    flex: 0 1 auto;
    gap: 0.3rem;
    min-width: 0;
  }

  .chip {
    flex: 0 1 auto;
    min-width: 3rem;
    max-width: 16rem;
    overflow: hidden;
    padding: 0.1rem 0.5rem;
    border: 1px solid var(--rule);
    border-radius: 999px;
    background: none;
    color: var(--pencil);
    font-size: 0.75rem;
    white-space: nowrap;
    text-overflow: ellipsis;
    cursor: pointer;
  }

  .chip:hover,
  .chip[aria-expanded='true'] {
    border-color: var(--pencil);
    color: var(--ink-soft);
  }

  .chip.full {
    border-color: var(--caution);
    color: var(--caution);
  }

  /* The writing box sits at the bottom, so its menus open upward over the chat. */
  .menu {
    position: absolute;
    bottom: calc(100% + 0.5rem);
    left: 0;
    z-index: 50;
    display: grid;
    gap: 0.4rem;
    width: min(22rem, 80vw);
    padding: 0.6rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: var(--shadow);
    user-select: none;
  }

  .label {
    font-size: var(--step--1);
    font-weight: 600;
    color: var(--ink-soft);
  }

  .options {
    display: grid;
  }

  .models {
    max-height: 14rem;
    overflow-y: auto;
  }

  .option {
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 0.5rem;
    padding: 0.3rem 0.45rem;
    border-radius: var(--radius);
    cursor: pointer;
  }

  .option:hover {
    background: var(--accent-wash);
  }

  .option input {
    grid-row: span 2;
    margin: 0.2rem 0 0;
    accent-color: var(--accent);
  }

  .option .name {
    color: var(--ink);
  }

  .meta,
  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .meta {
    grid-column: 2;
  }
</style>
