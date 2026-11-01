<script lang="ts">
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { spotlight, shown } from '../lib/spotlight';

  // Help is a map of what the learner can do, by level (ADR 0017): the app, the course, the section being read.
  // "Show me" closes Help and rings the real control where it sits, so the map teaches where things live.

  type Item = { title: MessageKey; text: MessageKey; target?: string; key?: string; open?: () => void };
  type Level = { title: MessageKey; items: Item[] };

  let dialog: HTMLDialogElement | undefined = $state();
  // Which controls are on screen is read when Help opens; the page behind it does not change while it is open.
  let visible = $state<Record<string, boolean>>({});

  const levels = $derived<Level[]>([
    {
      title: 'Throughline',
      items: [
        { title: 'All courses', text: 'Every course in your Throughline folder, and the course switcher beside it. Open one, or make a new one.', target: '#open-courses' },
        { title: 'Settings', text: 'Appearance and language, the teacher model and its effort, and updates.', target: '#open-settings' },
      ],
    },
    ...(app.state
      ? [
          {
            title: 'This course' as MessageKey,
            items: [
              { title: 'Route', text: 'Chapters and sections in teaching order, with where you are. Select one to look at it without moving.', target: '#route' },
              { title: 'Overview', text: 'The course as a whole: Studio, what the teacher remembers, sources and your notes. Study, Review and Overview are the course\'s three places.', target: '#open-course', key: 'm' },
              { title: 'Studio', text: 'Codex itself, working on your course. If you can describe a change, it can probably make it: new sections or exercises, added files, a different way of teaching.', key: 'd', open: () => app.showStudio({ focus: true }) },
              { title: 'Review', text: 'Questions to answer from memory on what you have studied, whenever you ask for them.', target: '#open-review' },
            ] as Item[],
          },
          {
            title: 'The section you are reading' as MessageKey,
            items: [
              { title: 'Lesson and practice', text: 'The lesson comes in steps; Continue moves on. Exercises follow, checked part by part.', target: '#main', key: 'c' },
              { title: 'Questions', text: 'Select a passage and choose Ask about this passage. The lesson keeps going while you ask.', target: '#toggle-questions', key: '/' },
              { title: 'Source', text: 'Click a citation to open the page it cites beside the lesson.', target: '#toggle-source', key: 's' },
              { title: 'Notes', text: 'Select text and choose Highlight or Note. Only you see them.', target: '#toggle-notes', key: 'n' },
            ] as Item[],
          },
        ]
      : []),
  ]);

  const keys: [string, MessageKey][] = [
    ['c', 'Continue the lesson'],
    ['/', 'Ask a side question'],
    ['[', 'Previous section'],
    [']', 'Next section'],
    ['s', 'Show or hide the source reader'],
    ['n', 'Show or hide your notes'],
    ['m', 'Show or hide the course page'],
    ['d', 'Show or hide Studio'],
    ['r', 'Fold or unfold the route'],
    ['Esc', 'Close a drawer or popup'],
    ['?', 'Show this help'],
  ];

  $effect(() => {
    if (!dialog) return;
    if (app.helpOpen && !dialog.open) {
      visible = Object.fromEntries(levels.flatMap((l) => l.items).filter((i) => i.target).map((i) => [i.target!, shown(i.target!)]));
      dialog.showModal();
    } else if (!app.helpOpen && dialog.open) dialog.close();
  });

  function show(item: Item) {
    app.helpOpen = false;
    // Wait for the dialog to close, so the ring is not drawn under its backdrop.
    requestAnimationFrame(() => (item.open ? item.open() : spotlight(item.target!)));
  }
</script>

<dialog bind:this={dialog} onclose={() => (app.helpOpen = false)} aria-labelledby="help-title">
  <header>
    <h2 id="help-title">{t('Help')}</h2>
    <p class="lead">{t('What you can do, from the whole app down to the section you are reading.')}</p>
  </header>

  <div class="levels">
    {#each levels as level (level.title)}
      <section aria-labelledby="help-{level.title}">
        <h3 id="help-{level.title}">{t(level.title)}</h3>
        <ul>
          {#each level.items as item (item.title)}
            <li>
              <div class="name">
                <span>{t(item.title)}</span>
                {#if item.key}<kbd>{item.key}</kbd>{/if}
              </div>
              <p>{t(item.text)}</p>
              {#if item.open || (item.target && visible[item.target])}
                <button class="btn btn-quiet btn-small btn-flush" onclick={() => show(item)}>{item.open ? t('Open') : t('Show me')}</button>
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/each}
  </div>

  <details class="keys">
    <summary>{t('Keyboard shortcuts')}</summary>
    <dl>
      {#each keys as [key, action]}
        <div><dt><kbd>{key}</kbd></dt><dd>{t(action)}</dd></div>
      {/each}
    </dl>
  </details>

  <button class="btn btn-small done" onclick={() => (app.helpOpen = false)}>{t('Done')}</button>
</dialog>

<style>
  dialog {
    width: min(58rem, calc(100vw - 2rem));
    max-height: calc(100vh - 3rem);
    padding: 1.5rem 1.6rem 1.25rem;
    border: 1px solid var(--rule);
    border-radius: 10px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }

  dialog::backdrop {
    background: rgb(17 20 27 / 0.35);
  }

  header {
    margin-bottom: 1.25rem;
  }

  h2 {
    font-family: var(--serif);
    font-size: var(--step-2);
    font-weight: 600;
  }

  .lead {
    margin-top: 0.3rem;
    color: var(--ink-soft);
  }

  .levels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 1.5rem;
  }

  h3 {
    margin-bottom: 0.6rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--rule);
    font-size: var(--step--1);
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--pencil);
  }

  ul {
    display: grid;
    gap: 0.9rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: grid;
    gap: 0.15rem;
    justify-items: start;
  }

  .name {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
  }

  li p {
    font-size: var(--step--1);
    line-height: 1.45;
    color: var(--ink-soft);
  }

  .keys {
    margin-top: 1.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--rule);
  }

  summary {
    font-weight: 600;
    cursor: pointer;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
    gap: 0.45rem 1.5rem;
    margin: 0.75rem 0 0;
  }

  dl div {
    display: grid;
    grid-template-columns: 3rem 1fr;
    align-items: center;
    font-size: var(--step--1);
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
    font-size: 0.75rem;
    font-weight: 400;
    text-align: center;
  }

  .done {
    display: block;
    margin: 1.25rem 0 0 auto;
  }
</style>
