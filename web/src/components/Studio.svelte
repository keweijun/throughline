<script lang="ts">
  import type { Completion, CompletionContext, CompletionSource } from '@codemirror/autocomplete';
  import type { EditorView } from '@codemirror/view';
  import { insertChip, type ChipRange } from '../lib/editor';
  import { t, type MessageKey } from '../lib/i18n.svelte';
  import { api } from '../lib/api';
  import { app } from '../lib/store.svelte';
  import { untrack } from 'svelte';
  import { studio, type StudioMessage, type StudioScope } from '../lib/studio.svelte';
  import Composer from './Composer.svelte';
  import StudioTurn from './StudioTurn.svelte';
  import StudioRequest from './StudioRequest.svelte';
  import CodexLink from './CodexLink.svelte';
  import StudioControls from './StudioControls.svelte';

  /**
   * Studio (ADR 0016): course work as a Codex chat. `$` suggests skills and `@` the course's files, both left in the
   * text as chips; images and files can be pasted, dropped or chosen; a message sent while Codex works steers it.
   * It is self-contained, so it can sit wherever it is mounted: `active` says it is on screen, and it scrolls whatever
   * scrolls it, keeping its writing box at that container's bottom.
   */
  // `scope` is where Studio is mounted: a course's Overview, or the library page before a course is open (#109).
  let { active = true, scope = 'course' }: { active?: boolean; scope?: StudioScope } = $props();

  let busy = $state(false);
  let attaching = $state(0);
  let view = $state.raw<EditorView>();
  // A request for the caret (`d`, a hand-off) is answered once Studio is on screen with its editor, even when it
  // mounts later than the request, say while the course is still loading.
  $effect(() => {
    const request = studio.focusRequest;
    if (!active || !view || request === studio.focusAnswered) return;
    studio.focusAnswered = request;
    const editor = view;
    requestAnimationFrame(() => editor.focus());
  });
  let chips: ChipRange[] = [];
  let recalled = 0;
  let list = $state<HTMLElement>();

  $effect(() => {
    const where = scope;
    // Moving the store is not something this effect reads, so two mounts never hand it back and forth.
    untrack(() => studio.setScope(where));
    if (active) void studio.load();
  });
  const library = $derived(scope === 'library');

  // Requests name the course by its folder, as the skill addresses courses; the learner sees its title.
  const course = $derived(library ? '' : (app.libraryCourse?.name ?? app.state?.course?.title ?? ''));
  const title = $derived(library ? '' : (app.state?.course?.title ?? course));
  const draftKey = $derived(`studio:${library ? 'library:' : ''}${studio.threadId ?? 'new'}`);
  const draft = $derived(app.drafts.get(draftKey));
  const images = $derived(app.drafts.images(draftKey));

  // Course work Studio can do, offered when a chat is empty; each fills the box rather than sending. Adding files
  // always shows; three more are drawn from the rest each time Studio opens, so the learner sees its range over time.
  const IDEAS: [MessageKey, MessageKey][] = [
    ['Check the pages that still need review', 'Review the pages of {course} that still need checking.'],
    ['Change how this course is taught', 'In {course},'],
    ['Turn a past exam into practice', 'In {course}, turn this past exam into practice in its style:'],
    ['Add a section the course is missing', 'In {course}, add a section on'],
    ['Fill in derivations the notes skip', 'In {course}, fill in the derivations my materials skip in chapter'],
    ['Add Python exercises to a chapter', 'In {course}, add Python exercises I can run to chapter'],
    ['Make a one-page cheat sheet', 'Make a one-page cheat sheet of {course} as a PDF, covering'],
    ['Make Anki cards of what I find hard', 'Make Anki cards from the difficulties in {course}.'],
    ['Teach this course in another language', 'From now on, teach {course} in'],
  ];
  const drawn = IDEAS.map((_, i) => i);
  for (let i = drawn.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [drawn[i], drawn[j]] = [drawn[j], drawn[i]];
  }
  const shown: [MessageKey, MessageKey][] = [
    ['Add files to this course', 'Add these files to {course}:'],
    ...drawn.slice(0, 3).sort((a, b) => a - b).map((i) => IDEAS[i]),
  ];
  // On the library page Studio is mostly how a course begins.
  const LIBRARY_IDEAS: [MessageKey, MessageKey][] = [
    ['Make a course from these files', 'Make a course from these files. I want to learn'],
    ['Make a course from a folder', 'Make a course from the files in the folder'],
    ['Make a course for an exam', 'Make a course for my exam on'],
  ];
  // A request that ends in a full stop is complete; the others leave the caret after a space for the learner to finish.
  const examples = $derived((library ? LIBRARY_IDEAS : shown).map(([label, text]) => {
    const request = t(text, { course });
    return { label: t(label), text: `$throughline ${request}${/[.。]$/.test(request) ? '' : ' '}` };
  }));

  const atWordStart = (context: CompletionContext, from: number) => from === 0 || /\s/.test(context.state.sliceDoc(from - 1, from));

  const skillSource: CompletionSource = (context) => {
    const word = context.matchBefore(/\$[\w:.-]*/);
    if (!word || !atWordStart(context, word.from) || !studio.skills.length) return null;
    return {
      from: word.from,
      validFor: /^\$[\w:.-]*$/,
      options: studio.skills.map((skill): Completion => ({
        label: `$${skill.name}`,
        detail: skill.title !== skill.name ? skill.title : undefined,
        info: skill.description || undefined,
        boost: skill.name === 'throughline' ? 2 : 0,
        apply: (v, _c, from, to) => insertChip(v, { kind: 'skill', name: skill.name, path: skill.path }, `$${skill.name}`, from, to),
      })),
    };
  };

  const fileSource: CompletionSource = async (context) => {
    const word = context.matchBefore(/@[^\s@]*/);
    if (!word || !atWordStart(context, word.from) || word.text.length < 2) return null;
    const files = await studio.search(word.text.slice(1)).catch(() => []);
    return {
      from: word.from,
      filter: false,
      options: files.map((file): Completion => ({
        label: `@${file.path}`,
        apply: (v, _c, from, to) => insertChip(v, { kind: 'mention', name: file.name, path: file.absolute }, `@${file.path}`, from, to),
      })),
    };
  };
  const completions = [skillSource, fileSource];

  /** The message as Codex's composer sends it: chips as spans (in code points) and what they name. A `$name` typed
   * without picking it, as in a request filled in from elsewhere, still names that skill. */
  function message(text: string): Omit<StudioMessage, 'images'> {
    const points = (index: number) => [...text.slice(0, index)].length;
    const found = chips.filter((c) => c.to <= text.length && text.slice(c.from, c.to).length === c.to - c.from);
    for (const match of text.matchAll(/(^|\s)\$([\w:.-]+)/g)) {
      const from = (match.index ?? 0) + match[1].length;
      const skill = studio.skills.find((s) => s.name === match[2]);
      if (skill && !found.some((c) => c.from === from)) found.push({ from, to: from + match[2].length + 1, chip: { kind: 'skill', name: skill.name, path: skill.path } });
    }
    found.sort((a, b) => a.from - b.from);
    const unique = <T extends { path: string }>(items: T[]) => items.filter((item, i) => items.findIndex((x) => x.path === item.path) === i);
    return {
      text,
      elements: found.map((c) => ({ start: points(c.from), end: points(c.to) })),
      skills: unique(found.filter((c) => c.chip.kind === 'skill').map((c) => ({ name: c.chip.name, path: c.chip.path }))),
      mentions: unique(found.filter((c) => c.chip.kind === 'mention').map((c) => ({ name: c.chip.name, path: c.chip.path }))),
    };
  }

  async function send() {
    if (busy) return;
    // The box takes a message while Codex is still starting; it goes out once Studio knows Codex can run it, and stays
    // in the box when Codex cannot.
    if (studio.available !== true) {
      busy = true;
      const ready = await studio.load().then(() => studio.available);
      busy = false;
      if (!ready) return;
    }
    const key = draftKey;
    const text = draft;
    const attached = images;
    const sent = message(text);
    // The box empties at once, as Codex's does, so the learner can write the next message while this one goes out;
    // a message that fails comes back if the box is still empty.
    busy = true;
    app.drafts.set(key, '');
    app.drafts.setImages(key, []);
    // On the library page, a chat remembers the courses there were when it began, to offer the one Codex makes.
    if (library && studio.coursesBefore === null) studio.coursesBefore = (app.library?.courses ?? []).map((c) => c.name);
    try {
      await studio.send({ ...sent, images: attached });
    } catch (e) {
      app.error = e instanceof Error ? e.message : String(e);
      if (!app.drafts.get(key)) app.drafts.set(key, text);
      if (!app.drafts.images(key).length) app.drafts.setImages(key, attached);
    }
    busy = false;
    recalled = 0;
  }

  /** Files are copied into the course's `inputs/` folder and named in the message, so Codex registers them there. */
  async function attachFiles(files: File[]) {
    for (const file of files) {
      attaching += 1;
      try {
        const saved = await studio.upload(file);
        if (view) insertChip(view, { kind: 'mention', name: saved.name, path: saved.absolute }, `@${saved.path}`);
      } catch (e) {
        app.error = e instanceof Error ? e.message : String(e);
      }
      attaching -= 1;
    }
  }

  // Courses that appeared in the library since this chat began, offered once Codex has finished with them.
  const made = $derived(
    library && studio.coursesBefore && !studio.running
      ? (app.library?.courses ?? []).filter((c) => !c.error && c.concepts && !studio.coursesBefore!.includes(c.name))
      : [],
  );

  // Opening the course files this chat under it and opens the course at its Studio, where the same chat carries on.
  let moving = false;
  async function openMade(name: string) {
    if (moving) return;
    moving = true;
    const thread = studio.threadId;
    if (thread) await app.act(() => api.post(`/api/studio/threads/${encodeURIComponent(thread)}/course`, { name }));
    app.askCourseStudio(name, '', thread);
  }

  // Once Codex has finished and the course it made has a route, the chat moves into that course by itself.
  $effect(() => {
    if (library && active && made.length === 1) void openMade(made[0].name);
  });

  function recall() {
    const sent = studio.sent;
    if (!sent.length) return null;
    recalled = Math.min(recalled + 1, sent.length);
    return sent[sent.length - recalled];
  }

  function fill(text: string) {
    app.drafts.set(draftKey, text);
    requestAnimationFrame(() => view?.focus());
  }

  /** What scrolls Studio: the frame its mount marks with `data-scroller`, else the nearest ancestor that scrolls now.
   * The mark matters while a chat is too short to scroll: otherwise the search would pass the frame and scroll the page. */
  function scrollParent(node: HTMLElement | undefined) {
    const marked = node?.closest<HTMLElement>('[data-scroller]');
    if (marked) return marked;
    for (let at = node?.parentElement; at; at = at.parentElement) {
      if (/(auto|scroll)/.test(getComputedStyle(at).overflowY) && at.scrollHeight > at.clientHeight) return at;
    }
    return null;
  }

  // The transcript follows new output while the learner is at its end, as a chat does.
  $effect(() => {
    const last = studio.turns.at(-1);
    void [studio.turns.length, last?.items.length, last?.status, JSON.stringify(last?.items.at(-1) ?? '').length, studio.pending.length];
    const scroller = scrollParent(list);
    if (!scroller) return;
    const near = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 160;
    if (near) requestAnimationFrame(() => (scroller.scrollTop = scroller.scrollHeight));
  });

  const threadLabel = (id: string) => {
    const thread = studio.threads.find((x) => x.id === id);
    return thread?.name || thread?.preview || t('Untitled chat');
  };
</script>

<section class="panel-view studio" aria-labelledby="studio-title">
  <header class="panel-head">
    <div class="panel-bar">
      <h2 id="studio-title">{t("Studio")}</h2>
    </div>
    <p class="panel-intro">{t("Create and change courses with Codex")}</p>
    {#if studio.available && (studio.threads.length || studio.threadId)}
      <div class="panel-tools">
        <select
          aria-label={t("Studio chats")}
          value={studio.threadId ?? ''}
          onchange={(event) => {
            const id = event.currentTarget.value;
            if (id) void studio.open(id);
            else studio.newThread();
          }}
        >
          <option value="">{t("New chat")}</option>
          {#each studio.threads as thread (thread.id)}
            <option value={thread.id}>{thread.running ? '● ' : ''}{threadLabel(thread.id)}</option>
          {/each}
        </select>
        <button class="btn btn-quiet btn-small" disabled={!studio.threadId} onclick={() => studio.newThread()}>{t("New chat")}</button>
      </div>
    {/if}
  </header>

  <div class="panel-list transcript" bind:this={list} aria-live="polite" aria-busy={studio.running}>
    {#if studio.available === false}
      <div class="unavailable">
        <p>{studio.error || t("Studio could not start Codex.")}</p>
        <CodexLink chat prompt={`$throughline ${course ? t('Open {course}', { course }) : ''}`} class="btn btn-small">{t("Open a Codex chat instead")}</CodexLink>
      </div>
    {:else if studio.available === null && studio.loading}
      <p class="panel-empty" role="status">{t("Starting Codex…")}</p>
    {:else if !studio.turns.length}
      <div class="welcome">
        {#if library}
          <h3 class="welcome-title">{t("What would you like to learn?")}</h3>
          <p class="panel-empty">{t("Drop your PDFs, slides or notes here, or name the folder they are in, and say what you want to learn. Codex reads them, asks you a few questions and builds the course.")}</p>
        {:else}
          <h3 class="welcome-title">{t("What would you like to change in this course?")}</h3>
          <p class="panel-empty">{t("This is Codex itself, working on this course. Ask for any change you can describe: new sections or exercises, files to add, a different way of teaching, something to take away. Questions about the material go to Questions.")}</p>
        {/if}
        <ul class="examples">
          {#each examples as example (example.label)}
            <li><button class="btn btn-quiet btn-small" onclick={() => fill(example.text)}>{example.label}</button></li>
          {/each}
        </ul>
      </div>
    {:else}
      {#each studio.turns as turn, i (turn.id)}
        <StudioTurn {turn} last={i === studio.turns.length - 1} />
      {/each}
    {/if}
    {#each studio.pending as request, i (request.id)}
      <StudioRequest {request} focus={active && i === 0} />
    {/each}
    {#if studio.error && studio.available}<p class="error" role="alert">{studio.error}</p>{/if}
  </div>

  {#snippet target()}
    <span class="target">
      {studio.threadId ? threadLabel(studio.threadId) : t("New chat")}{#if title}{' · '}{title}{/if}
      {#if studio.origin}
        <span class="origin" title={studio.origin.text}>
          <span class="origin-label">{studio.origin.label}</span>
          <button type="button" onclick={() => (studio.origin = null)} aria-label={t("Remove where this came from")} title={t("Remove where this came from")}>×</button>
        </span>
      {/if}
    </span>
  {/snippet}
  {#snippet tools()}
    {#if studio.running}
      <button type="button" class="btn btn-small stop" onclick={() => void studio.stop()} title={t("Stop Codex")}>
        <span class="square" aria-hidden="true"></span>{t("Stop")}
      </button>
    {/if}
    <StudioControls />
    {#if studio.context !== null}
      <span class="context" title={t("Share of the model's context this chat uses")}>{t("{percent}% context", { percent: Math.round(studio.context * 100) })}</span>
    {/if}
    {#if attaching}<span class="context" role="status">{t("Attaching…")}</span>{/if}
  {/snippet}
  <div class="panel-foot">
    {#each made as item (item.name)}
      <div class="made" role="status">
        <span>{t("Codex made the course {course}.", { course: item.title ?? item.name })}</span>
        <button class="btn btn-primary btn-small" onclick={() => openMade(item.name)}>{t("Open {course}", { course: item.title ?? item.name })}</button>
      </div>
    {/each}
    {#if studio.available !== false}
      <Composer
        id="studio-input"
        value={draft}
        onvalue={(value) => app.drafts.set(draftKey, value)}
        label={t("Message to Codex")}
        placeholder={studio.running ? t("Add to what Codex is doing…") : t("Ask Codex for course work · $ for skills, @ for files")}
        submitLabel={studio.running ? t("Add") : t("Send")}
        disabled={busy || attaching > 0}
        onsubmit={send}
        header={target}
        imagesKey={draftKey}
        imageScope={library ? 'library' : ''}
        imagesAlone
        preview={false}
        {completions}
        onchips={(found) => (chips = found)}
        onrecall={recall}
        onview={(editor) => (view = editor)}
        onfiles={attachFiles}
        {tools}
      />
    {/if}
  </div>
</section>

<style>
  /* Studio fills the frame it is mounted in, with its writing box at the bottom, so what loads above it (the welcome,
     a reopened chat) never moves the box from under the learner's pointer or caret. */
  .studio {
    display: flex;
    flex: 1 0 auto;
    flex-direction: column;
    min-height: 100%;
  }

  .transcript {
    display: flex;
    flex: 1 0 auto;
    flex-direction: column;
    gap: 1rem;
  }

  /* An empty chat asks its question in the middle of the frame, as a chat app does, with the ideas under it. */
  .welcome {
    display: grid;
    justify-items: center;
    gap: 0.75rem;
    max-width: 40rem;
    margin: auto;
    padding: 1.5rem 0;
    text-align: center;
  }

  .made {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1rem;
    padding: 0.6rem 0.8rem;
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    background: var(--accent-wash);
    font-weight: 600;
  }

  .welcome-title {
    font-family: var(--serif);
    font-size: var(--step-1);
    font-weight: 600;
    color: var(--ink);
  }

  .welcome .examples {
    justify-content: center;
  }

  .examples {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .examples .btn {
    border: 1px solid var(--rule-strong);
    border-radius: 999px;
    background: var(--raised);
    color: var(--ink);
    font-weight: 500;
  }

  .examples .btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .unavailable {
    display: grid;
    justify-items: start;
    gap: 0.6rem;
    font-size: var(--step--1);
    color: var(--ink-soft);
  }

  .error {
    margin: 0;
    font-size: var(--step--1);
    color: var(--danger);
  }

  .stop {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .square {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 2px;
    background: currentColor;
  }

  .context {
    flex: none;
    font-size: 0.75rem;
    color: var(--pencil);
    white-space: nowrap;
  }

  /* One row of tools however much Studio shows in it; its chips give way first (StudioControls). */
  .studio :global(.composer .bar) {
    flex-wrap: nowrap;
  }

  .studio :global(.composer .bar > *) {
    flex-shrink: 0;
  }

  .studio :global(.composer .bar > .controls) {
    flex-shrink: 1;
  }

  /* Where a hand-off came from, a chip in the box's header that the learner can take off before sending. */
  .origin {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    max-width: 14rem;
    margin-left: 0.4rem;
    padding: 0 0.15rem 0 0.45rem;
    border-radius: 999px;
    background: var(--accent-wash);
    color: var(--accent);
    vertical-align: middle;
  }

  .origin-label {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .origin button {
    padding: 0 0.3rem;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
</style>
