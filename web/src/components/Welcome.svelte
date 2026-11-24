<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '../lib/api';
  import { t, locale, type Language } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio } from '../lib/studio.svelte';
  import type { LauncherStatus } from '../lib/types';
  import LauncherHelp from './LauncherHelp.svelte';

  /**
   * The first time the library opens after installing (ADR 0017): a short series that sets the language, shows the
   * big picture (make a course in Studio, learn, review), says what makes Studio different and asks for its access,
   * and ends with how to open Throughline next time. A learner who already has courses only gets the last step, as
   * the launcher card was before; Help shows the middle two again.
   */
  type Step = 'language' | 'workflow' | 'studio' | 'launcher';

  let dialog = $state<HTMLDialogElement>();
  // Undefined until /api/launcher answers; null when it could not.
  let launcher = $state<LauncherStatus | null | undefined>(undefined);
  let steps = $state<Step[]>([]);
  let index = $state(0);
  // Which way the last move went, so the next step slides in from that side.
  let back = $state(false);
  let savingAccess = $state(false);
  // Whether the learner picked Studio's access here; until then a new learner's series sets Full access, the default.
  let pickedAccess = $state(false);

  const step = $derived(steps[index]);
  const last = $derived(index === steps.length - 1);
  const first = $derived(steps.includes('language'));

  let asked = false;
  $effect(() => {
    if (!app.libraryOpen || asked) return;
    asked = true;
    api.get<LauncherStatus>('/api/launcher').then((status) => (launcher = status), () => (launcher = null));
  });

  // Opens by itself once, on the library, when what decides it is known: the hints seen, the library and the launcher.
  // A learner with courses (or one in the trash) is not new, whatever was seen.
  let decided = false;
  $effect(() => {
    if (decided || !app.libraryOpen || !app.seen || !app.library || launcher === undefined) return;
    decided = true;
    const seen = app.seen;
    const fresh = !app.library.courses.length && !app.library.trash?.length && !seen.includes('launcher');
    const pointer = !!launcher?.exists && !seen.includes('launcher');
    if (fresh && !seen.includes('welcome')) untrack(() => open(['language', 'workflow', 'studio', ...(pointer ? ['launcher' as const] : [])]));
    else if (pointer) untrack(() => open(['launcher']));
  });

  // Help → "How Throughline works" shows the big picture again, from anywhere.
  $effect(() => {
    if (!app.welcomeAgain) return;
    app.welcomeAgain = false;
    untrack(() => open(['workflow', 'studio']));
  });

  // A new learner reaching the Studio step gets Full access, shown chosen, unless they pick Library access (ADR 0017).
  $effect(() => {
    if (step !== 'studio' || !first || pickedAccess || !studio.access || studio.access.full_access) return;
    untrack(() => void pickAccess(true, false));
  });

  function open(list: Step[]) {
    steps = list;
    index = 0;
    back = false;
    pickedAccess = false;
    if (list.includes('studio') && studio.access === null) void studio.loadAccess();
    queueMicrotask(() => {
      if (!dialog || dialog.open) return;
      dialog.showModal();
      // Enter moves on; the choices are a Tab away.
      dialog.querySelector<HTMLButtonElement>('footer .btn-primary')?.focus();
    });
  }

  function move(by: number) {
    back = by < 0;
    index += by;
  }

  // However the series ends (finished, skipped or Escape), it is not shown by itself again.
  function closed() {
    if (steps.includes('language')) app.markSeen('welcome');
    if (steps.includes('launcher')) app.markSeen('launcher');
    // The access was asked here, so the first course's introduction need not ask it again.
    if (steps.slice(0, index + 1).includes('studio')) app.markSeen('studio-access');
    steps = [];
  }

  function finish() {
    const wasFirst = first;
    dialog?.close();
    // A new learner's library is New course itself: put the caret in its box.
    if (wasFirst) {
      app.libraryView = 'new';
      studio.focusRequest++;
    }
  }

  async function pickAccess(full: boolean, byLearner = true) {
    if (byLearner) pickedAccess = true;
    if (full === !!studio.access?.full_access) return;
    savingAccess = true;
    try {
      await studio.setFullAccess(full);
    } catch (error) {
      app.error = error instanceof Error ? error.message : String(error);
    } finally {
      savingAccess = false;
    }
  }

  const examples = $derived([
    t('Add the problems in problem-set-3.pdf as exercises'),
    t('Make a one-page formula sheet for chapter 2'),
    t('Write a mock exam on what I have studied so far'),
    t('Teach chapter 3 with more rigour, from worked examples'),
  ]);
  // The Studio step's writing box shows one example request after another.
  let shown = $state(0);
  $effect(() => {
    if (step !== 'studio') return;
    shown = 0;
    const timer = setInterval(() => (shown = (shown + 1) % 4), 3200);
    return () => clearInterval(timer);
  });

  const titles = $derived<Record<Step, string>>({
    language: t('Choose your language'),
    workflow: t('How Throughline works'),
    studio: t('Codex works on your course'),
    launcher: t('Opening Throughline next time'),
  });

  const stages = $derived([
    { title: t('Make a course'), text: t('Bring your PDFs, slides or notes and say what you want to learn. Codex reads every page, asks about your goal and builds a route of chapters and sections.') },
    { title: t('Learn'), text: t('Each section is taught in steps, citing the pages it comes from. Select any passage to ask about it on the side; exercises are checked part by part.') },
    { title: t('Review'), text: t('Whenever you ask: questions from memory on what you have studied, a drill on a chapter, a mock exam.') },
  ]);
</script>

{#snippet logo(size: number)}
  <svg class="logo" viewBox="0 0 32 32" width={size} height={size} aria-hidden="true">
    <rect width="32" height="32" rx="7.5" fill="#24366e" />
    <path d="M6.5 9.2c3.4-1.5 6.6-1.5 9 0v15.6c-2.4-1.5-5.6-1.5-9 0z" fill="#fbfcfd" opacity=".78" />
    <path d="M16.5 9.2c2.4-1.5 5.6-1.5 9 0v15.6c-3.4-1.5-6.6-1.5-9 0z" fill="#fbfcfd" />
    <path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#24366e" stroke-width="4.6" stroke-linecap="round" />
    <path d="M3.8 20.6c4.6 0 6.3-6.9 12.2-6.9s7.6 6.9 12.2 6.9" fill="none" stroke="#f0d25c" stroke-width="2.5" stroke-linecap="round" />
  </svg>
{/snippet}

{#snippet stageIcon(i: number)}
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {#if i === 0}
      <path d="M6 3.5h8l4 4v13H6z" /><path d="M14 3.5v4h4" /><path d="M9 12.5h6M9 15.5h6M9 9.5h2.5" />
    {:else if i === 1}
      <path d="M3.5 5.5c3-1 6-1 8.5.8 2.5-1.8 5.5-1.8 8.5-.8v13c-3-1-6-1-8.5.8-2.5-1.8-5.5-1.8-8.5-.8z" /><path d="M12 6.3v13" />
    {:else}
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" /><path d="M19.5 4.5v3.5H16" /><path d="M9 12l2 2 4-4" />
    {/if}
  </svg>
{/snippet}

<dialog class="welcome" bind:this={dialog} onclose={closed} aria-labelledby="welcome-title">
  {#if step}
    <!-- Every step is laid in the same place and only the current one shows, so the dialog keeps the height of the
         tallest and its buttons stay put from step to step. -->
    <div class="steps">
    {#each steps as s (s)}
      <div class="step" class:current={s === step} class:back inert={s !== step}>
        <!-- Each step opens with a picture of what it is about; the words below carry everything it says. -->
        <div class="hero hero-{step}" aria-hidden="true">
          {#if s === 'language'}
            <div class="brand">
              {@render logo(56)}
              <span class="wordmark">Throughline <span class="sep">·</span> 贯学</span>
            </div>
          {:else if s === 'workflow'}
            <svg class="thread" viewBox="0 0 600 120" preserveAspectRatio="none">
              <path d="M-10 78 C40 78 60 60 100 60 S170 34 200 34 S260 60 300 60 S370 86 400 86 S460 60 500 60 S570 40 610 40" />
            </svg>
            <ol class="nodes">
              {#each stages as _, i (i)}
                <li><span class="node">{@render stageIcon(i)}</span></li>
              {/each}
            </ol>
          {:else if s === 'studio'}
            <div class="mock">
              <div class="mock-head">
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 15.5 13.5 6l1.8 1.8L5.8 17.3H4z" /><path d="M12 4.5 15.5 8" /><path d="M14.5 2.8 17.2 5.5" /></svg>
                {t('Studio')}
              </div>
              <div class="mock-box">
                {#key shown}
                  <span class="typed">{examples[shown]}<span class="caret"></span></span>
                {/key}
                <span class="send">
                  <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 15.5v-11M5.5 9 10 4.5 14.5 9" /></svg>
                </span>
              </div>
              <ol class="ticks">
                {#each examples as _, i (i)}<li class:on={i === shown}></li>{/each}
              </ol>
            </div>
          {:else if s === 'launcher'}
            <div class="dock">
              <span class="app"></span>
              <span class="app"></span>
              <span class="app mine">{@render logo(46)}</span>
              <span class="app"></span>
            </div>
          {/if}
        </div>

        <div class="body">
          {#if s === 'language'}
            <!-- Both languages, so either reader knows what is asked before choosing. -->
            <h2 id={s === step ? 'welcome-title' : undefined}>{locale.language === 'zh-CN' ? '选择语言 · Choose your language' : 'Choose your language · 选择语言'}</h2>
            <p class="lead">{t('Throughline shows everything in this language. A new course is taught in the language you write to Codex in, and your files keep their own.')}</p>
            <div class="tiles" role="radiogroup" aria-label={t('Language')}>
              {#each [['en', 'English', 'Aa'], ['zh-CN', '简体中文', '文']] as [id, name, glyph] (id)}
                <label class="tile">
                  <input type="radio" name="welcome-language" value={id} checked={locale.language === id} onchange={() => void app.setLanguage(id as Language)} />
                  <span class="glyph" aria-hidden="true">{glyph}</span>
                  <span class="name">{name}</span>
                  <span class="check" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4 8.3 6.8 11 12 5.2" /></svg></span>
                </label>
              {/each}
            </div>
            <p class="later">{t('You can change it in Settings → Appearance.')}</p>
          {:else if s === 'workflow'}
            <h2 id={s === step ? 'welcome-title' : undefined}>{titles.workflow}</h2>
            <ol class="stages">
              {#each stages as stage, i (i)}
                <li>
                  <h3>{stage.title}</h3>
                  <p>{stage.text}</p>
                </li>
              {/each}
            </ol>
          {:else if s === 'studio'}
            <h2 id={s === step ? 'welcome-title' : undefined}>{titles.studio}</h2>
            <p class="lead">{t('The teacher in Learn and Review is quick and answers about what you are reading. Studio is Codex itself: it can change the course whenever you ask, with your files and pages in reach.')}</p>
            <p class="where">{t("Studio is the first of each course's three places, beside Learn and Review, and New course opens it here. Learn and Review send it what they cannot do themselves.")}</p>
            <fieldset class="access" disabled={savingAccess || !studio.access}>
              <legend>{t('How much may Studio do without asking?')}</legend>
              {#if studio.access?.sandbox_missing}
                <p class="note">{t("Codex's sandbox is not set up on this Windows computer: Library access needs it.")}</p>
              {/if}
              <div class="tiles" role="radiogroup" aria-label={t('Access')}>
                <label class="tile option">
                  <input type="radio" name="welcome-access" checked={!!studio.access?.full_access} onchange={() => pickAccess(true)} />
                  <span class="icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M11.2 2.5 4.5 11.2h5l-.8 6.3 6.8-8.8h-5z" /></svg></span>
                  <span class="name">{t('Full access')}<span class="pill">{t('Recommended')}</span></span>
                  <span class="meta">{t('Codex can change files anywhere and runs commands without asking.')}</span>
                  <span class="check" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4 8.3 6.8 11 12 5.2" /></svg></span>
                </label>
                <label class="tile option">
                  <input type="radio" name="welcome-access" checked={!!studio.access && !studio.access.full_access} onchange={() => pickAccess(false)} />
                  <span class="icon" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M2.8 5.5h5l1.6 1.8h7.8v9.2H2.8z" /><path d="M8.2 12.2 10 14l3-3.3" /></svg></span>
                  <span class="name">{t('Library access')}</span>
                  <span class="meta">{t('Codex writes only inside your Throughline folder and asks before anything else.')}</span>
                  <span class="check" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="M4 8.3 6.8 11 12 5.2" /></svg></span>
                </label>
              </div>
              <p class="later">{t("You can change it any time in Studio's writing box.")}</p>
            </fieldset>
          {:else if s === 'launcher' && launcher}
            <h2 id={s === step ? 'welcome-title' : undefined}>{titles.launcher}</h2>
            <LauncherHelp {launcher} />
            <p class="later">{t('You can find this again in Settings → About.')}</p>
          {/if}
        </div>
      </div>
    {/each}
    </div>

    <footer>
      {#if steps.length > 1}
        <ol class="progress" aria-label={t('Step {n} of {total}', { n: index + 1, total: steps.length })}>
          {#each steps as s, i (s)}<li class:current={i === index} class:done={i < index}></li>{/each}
        </ol>
      {/if}
      <span class="grow"></span>
      {#if steps.length > 1 && !last}
        <button class="btn btn-quiet btn-small" onclick={() => dialog?.close()}>{t('Skip')}</button>
      {/if}
      {#if index > 0}
        <button class="btn btn-small" onclick={() => move(-1)}>{t('Back')}</button>
      {/if}
      {#if !last}
        <button class="btn btn-primary btn-small" onclick={() => move(1)}>{t('Next')}</button>
      {:else if first}
        <button class="btn btn-primary btn-small" onclick={finish}>{t('Make your first course')}</button>
      {:else}
        <button class="btn btn-primary btn-small" onclick={finish}>{steps.length > 1 ? t('Done') : t('Got it')}</button>
      {/if}
    </footer>
  {/if}
</dialog>

<style>
  .welcome {
    width: min(46rem, calc(100vw - 2rem));
    padding: 0;
    overflow: hidden;
    border: 1px solid var(--rule);
    border-radius: 14px;
    background: var(--sheet);
    color: var(--ink);
    box-shadow: var(--shadow);
  }
  .welcome::backdrop {
    background: rgb(17 20 27 / 0.5);
  }

  .steps {
    display: grid;
  }
  /* A step slides in from the side the learner is going to. */
  .step {
    grid-area: 1 / 1;
    visibility: hidden;
  }
  .step.current {
    visibility: visible;
    animation: step-in var(--settle) var(--ease-out);
  }
  .step.current.back {
    animation-name: step-back;
  }
  @keyframes step-in {
    from {
      opacity: 0;
      translate: 14px 0;
    }
  }
  @keyframes step-back {
    from {
      opacity: 0;
      translate: -14px 0;
    }
  }

  /* The picture at the top of each step. */
  .hero {
    position: relative;
    display: grid;
    place-items: center;
    height: 9.5rem;
    overflow: hidden;
    background:
      radial-gradient(120% 140% at 85% 0%, color-mix(in srgb, var(--marker) 18%, transparent), transparent 55%),
      linear-gradient(160deg, var(--accent-wash), color-mix(in srgb, var(--accent-wash) 40%, var(--sheet)));
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 12%, var(--rule));
  }

  .brand {
    display: grid;
    justify-items: center;
    gap: 0.7rem;
  }
  .logo {
    display: block;
    border-radius: 12px;
    box-shadow: 0 6px 18px color-mix(in srgb, var(--accent) 28%, transparent);
  }
  .wordmark {
    font: 600 1.25rem/1 var(--serif);
    letter-spacing: 0.01em;
    color: var(--accent);
  }
  .wordmark .sep {
    margin: 0 0.15em;
    color: var(--pencil);
  }

  /* The workflow: the logo's thread runs through the three stages. */
  .thread {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .thread path {
    fill: none;
    stroke: var(--marker);
    stroke-width: 5;
    stroke-linecap: round;
    vector-effect: non-scaling-stroke;
  }
  .nodes {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    margin: 0;
    padding: 0 1.75rem;
    list-style: none;
  }
  .nodes li {
    display: grid;
    place-items: center;
  }
  .node {
    display: grid;
    place-items: center;
    width: 3.6rem;
    height: 3.6rem;
    border: 2px solid var(--accent);
    border-radius: 50%;
    background: var(--sheet);
    box-shadow: 0 0 0 6px color-mix(in srgb, var(--sheet) 55%, transparent);
  }
  .node svg,
  .icon svg {
    fill: none;
    stroke: var(--accent);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .node svg {
    width: 1.6rem;
    height: 1.6rem;
  }

  /* Studio: its writing box, filling with one request after another. */
  .mock {
    display: grid;
    gap: 0.45rem;
    width: min(30rem, 82%);
  }
  .mock-head {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font: 600 var(--step--1) / 1 var(--sans);
    color: var(--accent);
  }
  .mock-head svg {
    width: 0.95rem;
    height: 0.95rem;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .mock-box {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-height: 3.1rem;
    padding: 0.55rem 0.55rem 0.55rem 0.95rem;
    border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--rule));
    border-radius: 12px;
    background: var(--raised);
    box-shadow: 0 8px 22px color-mix(in srgb, var(--accent) 14%, transparent);
  }
  .typed {
    flex: 1;
    font-size: var(--step-0);
    animation: enter-fade var(--settle) ease;
  }
  .caret {
    display: inline-block;
    width: 2px;
    height: 1.05em;
    margin-left: 2px;
    vertical-align: -0.15em;
    background: var(--accent);
    animation: blink 1.1s steps(1) infinite;
  }
  @keyframes blink {
    50% {
      opacity: 0;
    }
  }
  .send {
    display: grid;
    flex: none;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: var(--accent);
  }
  .send svg {
    width: 1rem;
    height: 1rem;
    fill: none;
    stroke: var(--on-accent);
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .ticks {
    display: flex;
    justify-content: center;
    gap: 0.3rem;
    margin: 0.2rem 0 0;
    padding: 0;
    list-style: none;
  }
  .ticks li {
    width: 0.9rem;
    height: 3px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    transition: background var(--quick, 120ms) ease;
  }
  .ticks li.on {
    background: var(--accent);
  }

  /* The launcher: Throughline in a dock. */
  .dock {
    display: flex;
    align-items: flex-end;
    gap: 0.7rem;
    padding: 0.6rem 0.8rem;
    border: 1px solid color-mix(in srgb, var(--accent) 15%, var(--rule));
    border-radius: 16px;
    background: color-mix(in srgb, var(--sheet) 70%, transparent);
    box-shadow: 0 8px 22px color-mix(in srgb, var(--accent) 12%, transparent);
  }
  .app {
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 10px;
    background: color-mix(in srgb, var(--pencil) 22%, var(--sheet));
  }
  .app.mine {
    position: relative;
    width: auto;
    height: auto;
    background: none;
    translate: 0 -0.35rem;
  }
  .app.mine::after {
    content: '';
    position: absolute;
    bottom: -0.55rem;
    left: 50%;
    width: 0.3rem;
    height: 0.3rem;
    margin-left: -0.15rem;
    border-radius: 50%;
    background: var(--accent);
  }

  /* The words. */
  .body {
    display: grid;
    align-content: start;
    gap: 0.8rem;
    min-height: 15.5rem;
    padding: 1.4rem 1.75rem 0.4rem;
  }
  h2 {
    font: 600 var(--step-2) / 1.25 var(--serif);
    letter-spacing: -0.005em;
  }
  .lead {
    color: var(--ink-soft);
    line-height: 1.55;
  }
  .later,
  .where,
  .note {
    font-size: var(--step--1);
    color: var(--pencil);
  }

  .stages {
    counter-reset: stage;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.5rem;
    margin: 0.2rem 0 0;
    padding: 0;
    list-style: none;
  }
  .stages h3 {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 0.4rem;
    font: 600 var(--step-0) / 1.3 var(--sans);
  }
  /* The stage's number, drawn, as the list already says it. */
  .stages h3::before {
    counter-increment: stage;
    content: counter(stage);
    display: grid;
    place-items: center;
    flex: none;
    width: 1.35rem;
    height: 1.35rem;
    border-radius: 50%;
    background: var(--accent);
    color: var(--on-accent);
    font-size: 0.72rem;
  }
  .stages p {
    font-size: var(--step--1);
    line-height: 1.55;
    color: var(--ink-soft);
  }

  /* Choices as tiles: the whole tile is the radio button. */
  .tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.7rem;
  }
  .tile {
    position: relative;
    display: grid;
    grid-template-columns: auto 1fr;
    column-gap: 0.8rem;
    align-items: center;
    padding: 0.85rem 2.4rem 0.85rem 0.9rem;
    border: 1.5px solid var(--rule);
    border-radius: 10px;
    background: var(--raised);
    cursor: pointer;
    transition:
      border-color var(--quick, 120ms) ease,
      background-color var(--quick, 120ms) ease,
      box-shadow var(--quick, 120ms) ease;
  }
  .tile:hover {
    border-color: color-mix(in srgb, var(--accent) 45%, var(--rule));
  }
  .tile:has(input:checked) {
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent-wash) 45%, var(--raised));
  }
  .tile:has(input:focus-visible) {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  /* The real radio button covers the tile, unseen, so it takes the click and the keyboard. */
  .tile input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    cursor: pointer;
  }
  .glyph,
  .icon {
    display: grid;
    place-items: center;
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 8px;
    background: var(--accent-wash);
    color: var(--accent);
  }
  .glyph {
    font: 600 1.25rem/1 var(--serif);
  }
  /* An access option reads top to bottom: its icon, its name, what it lets Codex do. Both options line up. */
  .option {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.25rem;
    padding: 1rem 1.05rem 1.05rem;
  }
  .option .icon {
    width: 2.2rem;
    height: 2.2rem;
    margin-bottom: 0.45rem;
  }
  .option .name {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }
  .option .meta {
    margin-top: 0;
  }
  .option:has(input:checked) .icon {
    background: var(--accent);
  }
  .option:has(input:checked) .icon svg {
    stroke: var(--on-accent);
  }
  .icon svg {
    width: 1.25rem;
    height: 1.25rem;
  }
  .tile .name {
    font-weight: 600;
  }
  .tile .meta {
    grid-column: 2;
    margin-top: 0.15rem;
    font-size: var(--step--1);
    line-height: 1.45;
    color: var(--pencil);
  }
  .pill {
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--marker) 55%, transparent);
    color: light-dark(#5a4600, #f3dc84);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  .check {
    position: absolute;
    top: 0.7rem;
    right: 0.7rem;
    display: grid;
    place-items: center;
    width: 1.15rem;
    height: 1.15rem;
    border: 1.5px solid var(--rule-strong);
    border-radius: 50%;
  }
  .check svg {
    width: 0.8rem;
    height: 0.8rem;
    fill: none;
    stroke: var(--on-accent);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0;
  }
  .tile:has(input:checked) .check {
    border-color: var(--accent);
    background: var(--accent);
  }
  .tile:has(input:checked) .check svg {
    opacity: 1;
  }

  .access {
    display: grid;
    gap: 0.55rem;
    margin: 0.3rem 0 0;
    padding: 0;
    border: 0;
  }
  .access legend {
    margin-bottom: 0.55rem;
    padding: 0;
    font-weight: 600;
  }

  footer {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem 1.75rem 1.25rem;
  }
  .progress {
    display: flex;
    gap: 0.3rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .progress li {
    width: 1.1rem;
    height: 4px;
    border-radius: 2px;
    background: var(--rule);
    transition:
      width var(--settle) var(--ease-out),
      background-color var(--settle) ease;
  }
  .progress li.done {
    background: color-mix(in srgb, var(--accent) 45%, var(--rule));
  }
  .progress li.current {
    width: 2rem;
    background: var(--accent);
  }
  .grow {
    flex: 1;
  }
</style>
