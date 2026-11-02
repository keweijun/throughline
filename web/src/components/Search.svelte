<script lang="ts">
  import { tick } from 'svelte';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { api } from '../lib/api';
  import { labelFor } from '../lib/markdown';
  import { GROUPS, index, search, sourceHit, type Group, type Hit, type Snippet } from '../lib/search';
  import type { Ref } from '../lib/types';

  // Search across the course, opened with Shift twice as in JetBrains IDEs, or Ctrl+K. Everything but source text is
  // searched in the state as the learner types; source text is searched by the host a moment after they stop. As in
  // JetBrains' Search Everywhere, All shows the best hits of every category and a category's tab shows all of its own;
  // Tab moves between them.

  const SHOWN = 5; // hits per category under All
  const NAMES = { sections: 'Sections', lessons: 'Lessons', questions: 'Questions', exercises: 'Exercises', notes: 'Notes', sources: 'Sources' } as const;
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);

  type SourceUnit = Ref & { path: string; excerpt: string };
  type Row = { id: string } & ({ hit: Hit } | { group: Group; count: number });
  type Category = 'all' | Group;
  const CATEGORIES: Category[] = ['all', ...GROUPS];

  let dialog = $state<HTMLDialogElement>();
  let input = $state<HTMLInputElement>();
  let query = $state('');
  let active = $state(0);
  // The category stays between searches, as the last query does.
  let category = $state<Category>('all');
  let sources = $state.raw<{ query: string; hits: Hit[]; more: boolean } | null>(null);
  let searching = $state(false);

  // The course is indexed while search is open, so a closed search costs nothing as the state changes.
  const items = $derived(app.searchOpen && app.state ? index(app.state) : []);
  const words = $derived(query.trim());
  // The chapter on the page ranks first among hits that are otherwise alike.
  const near = $derived(new Set(app.chapters.find((c) => c.id === app.chapterInView)?.concept_ids ?? []));
  const hits = $derived([...search(items, words, near), ...(sources?.query === words ? sources.hits : [])]);
  const counts = $derived(Object.fromEntries(GROUPS.map((g) => [g, hits.filter((h) => h.group === g).length])) as Record<Group, number>);
  const groups = $derived(
    GROUPS.filter((group) => category === 'all' || category === group).map((group) => {
      const all = hits.filter((h) => h.group === group);
      const shown = category === 'all' ? all.slice(0, SHOWN) : all;
      const rows: Row[] = shown.map((hit) => ({ id: hit.key, hit }));
      if (all.length > shown.length) rows.push({ id: `more:${group}`, group, count: all.length - shown.length });
      return { group, rows };
    }).filter((g) => g.rows.length),
  );
  const rows = $derived(groups.flatMap((g) => g.rows));

  $effect(() => {
    if (!dialog) return;
    if (app.searchOpen && !dialog.open) {
      dialog.showModal();
      // The last search stays, selected, so typing replaces it and Enter repeats it.
      input?.select();
    } else if (!app.searchOpen && dialog.open) dialog.close();
  });

  // A new query or category starts at its best hit.
  $effect(() => {
    void words;
    void category;
    active = 0;
    document.getElementById('search-results')?.scrollTo({ top: 0 });
  });

  $effect(() => {
    const asked = words;
    if (!app.searchOpen || !asked) {
      searching = false;
      return;
    }
    searching = true;
    const timer = setTimeout(async () => {
      try {
        const found = await api.get<{ units: SourceUnit[]; more: boolean }>(`/api/search/sources?q=${encodeURIComponent(asked)}`);
        if (asked === words) sources = { query: asked, hits: found.units.map((u) => sourceHit(u, asked, labelFor(u))), more: found.more };
      } catch {
        if (asked === words) sources = { query: asked, hits: [], more: false };
      } finally {
        if (asked === words) searching = false;
      }
    }, 200);
    return () => clearTimeout(timer);
  });

  async function move(by: number) {
    if (!rows.length) return;
    active = (active + by + rows.length) % rows.length;
    await tick();
    document.getElementById(`search-row-${active}`)?.scrollIntoView({ block: 'nearest' });
  }

  function choose(row: Row | undefined) {
    if (!row) return;
    if ('hit' in row) void app.reveal(row.hit.target);
    else select(row.group);
  }

  function select(next: Category) {
    category = next;
    input?.focus();
  }

  function onKey(event: KeyboardEvent) {
    if (event.isComposing) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      app.searchOpen = false;
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      void move(event.key === 'ArrowDown' ? 1 : -1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      choose(rows[active]);
    } else if (event.key === 'Tab') {
      event.preventDefault();
      const at = CATEGORIES.indexOf(category) + (event.shiftKey ? -1 : 1);
      category = CATEGORIES[(at + CATEGORIES.length) % CATEGORIES.length];
    }
  }

  function pieces(snippet: Snippet) {
    const out: { text: string; marked: boolean }[] = [];
    let at = 0;
    for (const [start, end] of snippet.marks) {
      if (start > at) out.push({ text: snippet.text.slice(at, start), marked: false });
      out.push({ text: snippet.text.slice(start, end), marked: true });
      at = end;
    }
    if (at < snippet.text.length) out.push({ text: snippet.text.slice(at), marked: false });
    return out;
  }

  const position = (row: Row) => rows.indexOf(row);
</script>

<dialog
  bind:this={dialog}
  class="search"
  aria-label={t('Search this course')}
  onclose={() => {
    // The close event comes a moment after closing; by then search may have been opened again.
    if (!dialog?.open) app.searchOpen = false;
  }}
  onclick={(event) => event.target === dialog && (app.searchOpen = false)}
>
  <div class="tabs" role="tablist" aria-label={t('Search in')}>
    {#each CATEGORIES as each (each)}
      {@const count = each === 'all' ? hits.length : counts[each]}
      <button role="tab" tabindex="-1" aria-selected={category === each} aria-controls="search-results" onclick={() => select(each)}>
        {t(each === 'all' ? 'All' : NAMES[each])}{#if words && count}<span class="count">{(each === 'sources' || each === 'all') && sources?.query === words && sources.more ? `${count}+` : count}</span>{/if}
      </button>
    {/each}
  </div>

  <div class="field">
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.6" fill="none" stroke="currentColor" stroke-width="1.6" /><path d="m12.8 12.8 4.4 4.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
    <input
      bind:this={input}
      bind:value={query}
      onkeydown={onKey}
      type="text"
      placeholder={t('Search this course')}
      aria-label={t('Search this course')}
      role="combobox"
      aria-expanded={rows.length > 0}
      aria-controls="search-results"
      aria-activedescendant={rows.length ? `search-row-${active}` : undefined}
      autocomplete="off"
      spellcheck="false"
    />
  </div>

  <div class="results" id="search-results" role="listbox" aria-label={t('Search results')}>
    {#each groups as group (group.group)}
      <div class="group" role="group" aria-label={t(NAMES[group.group])}>
        {#if category === 'all'}<h3>{t(NAMES[group.group])}</h3>{/if}
        {#each group.rows as row (row.id)}
          {@const at = position(row)}
          <!-- svelte-ignore a11y_click_events_have_key_events (the input moves through the rows and opens them) -->
          <div
            id="search-row-{at}"
            class="row"
            class:active={at === active}
            role="option"
            tabindex="-1"
            aria-selected={at === active}
            onclick={() => choose(row)}
            onpointermove={() => (active = at)}
          >
            {#if 'hit' in row}
              <div class="title">
                <span>{row.hit.title}</span>
                {#if row.hit.context}<span class="context">{row.hit.context}</span>{/if}
              </div>
              {#if row.hit.snippet.text && row.hit.snippet.text !== row.hit.title}
                <p class="snippet">{#each pieces(row.hit.snippet) as piece}{#if piece.marked}<mark>{piece.text}</mark>{:else}{piece.text}{/if}{/each}</p>
              {/if}
            {:else}
              <span class="more">{t('Show {count} more', { count: row.count })}</span>
            {/if}
          </div>
        {/each}
        {#if group.group === 'sources' && sources?.more && sources.query === words}
          <p class="note">{t('More source pages match. Add a word to narrow the search.')}</p>
        {/if}
      </div>
    {/each}

    {#if !words}
      <p class="note">{t('Section and chapter titles, lessons, your questions and their answers, exercises with your answers, notes and sources.')}</p>
    {:else if !rows.length && !searching}
      <p class="note">
        {category === 'all' ? t('Nothing in this course matches “{query}”.', { query: words }) : t('Nothing in {category} matches “{query}”.', { category: t(NAMES[category]), query: words })}
      </p>
    {/if}
    {#if searching}
      <p class="note" role="status">{t('Searching sources…')}</p>
    {/if}
  </div>

  <footer>
    <span><kbd>↑</kbd><kbd>↓</kbd> {t('to move')}</span>
    <span><kbd>Enter</kbd> {t('to open')}</span>
    <span><kbd>Tab</kbd> {t('to switch category')}</span>
    <span><kbd>Esc</kbd> {t('to close')}</span>
    <span class="shortcut">Shift Shift · {mac ? '⌘K' : 'Ctrl+K'}</span>
  </footer>
</dialog>

<style>
  dialog {
    width: min(46rem, calc(100vw - 2rem));
    max-height: min(40rem, calc(100vh - 6rem));
    margin: 9vh auto auto;
    padding: 0;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
    flex-direction: column;
    overflow: hidden;
  }

  dialog[open] {
    display: flex;
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.35);
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
    padding: 0.55rem 0.8rem 0.45rem;
    border-bottom: 1px solid var(--rule);
  }

  .tabs button {
    display: inline-flex;
    align-items: baseline;
    gap: 0.35rem;
    padding: 0.25rem 0.65rem;
    border: 1px solid transparent;
    border-radius: var(--radius);
    background: none;
    color: var(--ink-soft);
    font: inherit;
    font-size: var(--step--1);
    cursor: pointer;
  }

  .tabs button:hover {
    color: var(--ink);
    background: var(--raised);
  }

  .tabs button[aria-selected='true'] {
    border-color: var(--accent);
    background: var(--accent-wash);
    color: var(--accent);
    font-weight: 600;
  }

  .count {
    font-size: 0.72rem;
    font-weight: 400;
    color: var(--pencil);
  }

  .field {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.85rem 1.1rem;
    border-bottom: 1px solid var(--rule);
    color: var(--pencil);
  }

  input {
    flex: 1;
    min-width: 0;
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--ink);
    font: inherit;
    font-size: var(--step-1);
  }

  .results {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0.35rem 0 0.6rem;
  }

  h3 {
    margin: 0.6rem 1.1rem 0.2rem;
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  .row {
    margin: 0 0.45rem;
    padding: 0.4rem 0.65rem;
    border-radius: var(--radius);
    cursor: pointer;
  }

  .row.active {
    background: var(--accent-wash);
  }

  .title {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    min-width: 0;
    font-weight: 600;
  }

  .title span:first-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .context {
    flex-shrink: 0;
    max-width: 40%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--step--1);
    font-weight: 400;
    color: var(--pencil);
  }

  .snippet {
    display: -webkit-box;
    margin-top: 0.1rem;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    font-size: var(--step--1);
    line-height: 1.45;
    color: var(--ink-soft);
    overflow-wrap: anywhere;
  }

  mark {
    border-radius: 2px;
    background: var(--marker-wash);
    color: inherit;
  }

  .more {
    font-size: var(--step--1);
    color: var(--accent);
  }

  .note {
    margin: 0.6rem 1.1rem 0;
    font-size: var(--step--1);
    color: var(--pencil);
  }

  footer {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.1rem;
    padding: 0.55rem 1.1rem;
    border-top: 1px solid var(--rule);
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .shortcut {
    margin-left: auto;
  }

  kbd {
    display: inline-block;
    min-width: 1.4rem;
    margin-right: 0.15rem;
    padding: 0 0.3rem;
    border: 1px solid var(--rule-strong);
    border-bottom-width: 2px;
    border-radius: 4px;
    background: var(--raised);
    font-family: var(--mono);
    font-size: 0.72rem;
    text-align: center;
  }
</style>
