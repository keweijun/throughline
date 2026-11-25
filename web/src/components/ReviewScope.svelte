<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { pop } from '../lib/motion';
  import { reviewable as studied, type ReviewScope } from '../lib/scope.svelte';

  /**
   * What the Review place covers, as one button that names it. It opens a picker over the page, so choosing never moves
   * what is under it: everything studied, or whole chapters and single sections of them. With none chosen it covers
   * everything studied.
   */
  let { value, onchange }: { value: ReviewScope; onchange: (value: ReviewScope) => void } = $props();

  const chapters = $derived(
    app.chapters.map((c) => ({ ...c, studied: c.concept_ids.filter(studied) })).filter((c) => c.studied.length),
  );
  const everything = $derived(!value.chapter_ids.length && !value.concept_ids.length);
  const title = (id: string) => app.concept(id)?.title ?? id;
  // In the course's order: a chapter chosen whole by its title, else its sections chosen.
  const chosen = $derived(
    chapters.flatMap((c) => (value.chapter_ids.includes(c.id) ? [c.title] : c.studied.filter((id) => value.concept_ids.includes(id)).map(title))),
  );
  // Two names at most on the button; the rest are counted, and all of them are in its tooltip.
  const name = $derived(
    everything
      ? t('Everything studied')
      : chosen.length > 2
        ? t('{names} and {count} more', { names: chosen.slice(0, 2).join(', '), count: chosen.length - 2 })
        : chosen.join(', '),
  );

  // A long course folds its chapters, and a chapter opens to choose single sections; one with sections chosen starts
  // open. With that many, a filter finds a section by name.
  const total = $derived(chapters.reduce((n, c) => n + c.studied.length, 0));
  const folding = $derived(total > 14 && !app.wholeCourse);
  let unfolded = $state<string[]>([]);
  let filter = $state('');
  const unfold = (id: string) => (unfolded = unfolded.includes(id) ? unfolded.filter((x) => x !== id) : [...unfolded, id]);
  const showsSections = (item: (typeof chapters)[number]) => !folding || !!filter.trim() || unfolded.includes(item.id);
  const matches = (item: (typeof chapters)[number]) => {
    const words = filter.trim().toLowerCase();
    if (!words) return item.studied;
    return item.title.toLowerCase().includes(words) ? item.studied : item.studied.filter((id) => title(id).toLowerCase().includes(words));
  };
  function toggle() {
    open = !open;
    if (open) {
      filter = '';
      unfolded = chapters.filter((c) => some(c)).map((c) => c.id);
    }
  }

  let open = $state(false);
  let root = $state<HTMLElement>();
  $effect(() => {
    if (!open) return;
    const away = (event: Event) => root && !root.contains(event.target as Node) && (open = false);
    const escape = (event: KeyboardEvent) => event.key === 'Escape' && (open = false);
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', escape);
    };
  });

  const whole = (id: string) => value.chapter_ids.includes(id);
  const some = (chapter: (typeof chapters)[number]) => !whole(chapter.id) && chapter.studied.some((id) => value.concept_ids.includes(id));

  function chapter(item: (typeof chapters)[number]) {
    // A chapter chosen whole covers its sections; they stop being separate choices.
    const others = value.concept_ids.filter((id) => !item.concept_ids.includes(id));
    onchange({ chapter_ids: whole(item.id) ? value.chapter_ids.filter((x) => x !== item.id) : [...value.chapter_ids, item.id], concept_ids: others });
  }

  function section(item: (typeof chapters)[number], id: string) {
    if (whole(item.id)) {
      // Taking one section out of a whole chapter leaves the rest of it chosen.
      onchange({ chapter_ids: value.chapter_ids.filter((x) => x !== item.id), concept_ids: [...value.concept_ids, ...item.studied.filter((x) => x !== id)] });
      return;
    }
    const ids = value.concept_ids.includes(id) ? value.concept_ids.filter((x) => x !== id) : [...value.concept_ids, id];
    // Every studied section of a chapter chosen is the chapter.
    if (item.studied.every((x) => ids.includes(x))) {
      onchange({ chapter_ids: [...value.chapter_ids, item.id], concept_ids: ids.filter((x) => !item.concept_ids.includes(x)) });
    } else onchange({ ...value, concept_ids: ids });
  }
</script>

<div class="scope" bind:this={root}>
  <button class="pick" aria-haspopup="true" aria-expanded={open} title={name} onclick={toggle}>
    <span class="label">{t('Covering')}</span>
    <span class="name">{name}</span>
    <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5.5 8l4.5 4.5L14.5 8" /></svg>
  </button>
  {#if open}
    <div class="picker" class:folding role="group" aria-label={t('What to review')} transition:pop={{ from: 'above' }}>
      <label class="all">
        <input type="radio" checked={everything} onchange={() => onchange({ chapter_ids: [], concept_ids: [] })} />
        {t('Everything studied')}
      </label>
      {#if folding}
        <input class="filter" type="search" placeholder={t('Find a chapter or section')} aria-label={t('Find a chapter or section')} bind:value={filter} />
      {/if}
      {#each chapters.filter((c) => matches(c).length) as item (item.id)}
        <fieldset>
          <legend class="visually-hidden">{item.title}</legend>
          <!-- A course without chapters is one chapter named after the course: its sections are the choices. -->
          {#if !app.wholeCourse}
            <div class="chapter-row">
              <label class="chapter">
                <input type="checkbox" checked={whole(item.id)} indeterminate={some(item)} onchange={() => chapter(item)} />
                <span class="chapter-title">{item.title}</span>
              </label>
              {#if folding && !filter.trim()}
                <button type="button" class="fold" aria-expanded={unfolded.includes(item.id)} aria-label={t('Sections of {chapter}', { chapter: item.title })} onclick={() => unfold(item.id)}>
                  <span class="sections-count">{some(item) ? t('{chosen} of {count}', { chosen: item.studied.filter((id) => value.concept_ids.includes(id)).length, count: item.studied.length }) : item.studied.length}</span>
                  <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true"><path d="M5.5 8l4.5 4.5L14.5 8" /></svg>
                </button>
              {/if}
            </div>
          {/if}
          {#each showsSections(item) ? matches(item) : [] as id (id)}
            <label class="section">
              <input type="checkbox" checked={whole(item.id) || value.concept_ids.includes(id)} onchange={() => section(item, id)} />
              {title(id)}
            </label>
          {/each}
        </fieldset>
      {/each}
    </div>
  {/if}
</div>

<style>
  .scope {
    position: relative;
    min-width: 0;
  }

  .pick {
    display: inline-flex;
    align-items: baseline;
    gap: 0.4rem;
    max-width: 100%;
    padding: 0.3rem 0.65rem;
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: var(--sheet);
    color: var(--ink);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
    transition: border-color 0.15s ease;
  }

  .pick:hover,
  .pick[aria-expanded='true'] {
    border-color: var(--pencil);
  }

  .label {
    color: var(--pencil);
  }

  .name {
    min-width: 0;
    overflow: hidden;
    font-weight: 600;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  svg {
    flex: none;
    align-self: center;
    fill: none;
    stroke: var(--pencil);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  /* Over the page, from the button, the same look as the course's menu in Studio. */
  .picker {
    position: absolute;
    top: calc(100% + 0.4rem);
    right: 0;
    z-index: 40;
    display: grid;
    gap: 0.6rem;
    width: min(22rem, calc(100vw - 2rem));
    max-height: min(28rem, calc(100dvh - 10rem));
    overflow-y: auto;
    padding: 0.6rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    box-shadow: var(--shadow);
  }

  .filter {
    width: 100%;
    padding: 0.35rem 0.55rem;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius);
    background: var(--raised);
    color: var(--ink);
    font: inherit;
    font-size: var(--step--1);
  }

  .filter:focus {
    border-color: var(--accent);
    outline: none;
  }

  .chapter-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .chapter-row .chapter {
    flex: 1;
    min-width: 0;
  }

  .chapter-title {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .fold {
    display: inline-flex;
    flex: none;
    align-items: center;
    gap: 0.3rem;
    padding: 0.3rem 0.45rem;
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--pencil);
    font: inherit;
    font-size: var(--step--2, 0.75rem);
    cursor: pointer;
  }

  .fold:hover {
    background: var(--raised);
    color: var(--ink);
  }

  .fold[aria-expanded='true'] svg {
    rotate: 180deg;
  }

  .fold svg {
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: rotate 0.15s ease;
  }

  fieldset {
    display: grid;
    margin: 0;
    padding: 0.5rem 0 0;
    border: 0;
    border-top: 1px solid var(--rule);
  }

  /* Folded, the chapters are one list: a rule only above the first, and between a chapter opened and the next. */
  .folding fieldset {
    padding-top: 0.1rem;
    border-top: 0;
  }

  .folding .filter + fieldset,
  .folding fieldset:has(.section) + fieldset {
    margin-top: 0.3rem;
    padding-top: 0.4rem;
    border-top: 1px solid var(--rule);
  }

  label {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.3rem 0.45rem;
    border-radius: var(--radius);
    font-size: var(--step--1);
    color: var(--ink-soft);
    cursor: pointer;
  }

  label:hover {
    background: var(--raised);
    color: var(--ink);
  }

  .all,
  .chapter {
    font-weight: 600;
    color: var(--ink);
  }

  .chapter-row ~ .section {
    padding-left: 1.75rem;
  }

  input {
    flex: none;
    margin: 0;
    accent-color: var(--accent);
  }
</style>
