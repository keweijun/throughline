<script lang="ts">
  import type { Completion, CompletionContext, CompletionSource } from '@codemirror/autocomplete';
  import type { EditorView } from '@codemirror/view';
  import { insertChip, type ChipRange } from '../lib/editor';
  import { t } from '../lib/i18n.svelte';
  import { app } from '../lib/store.svelte';
  import { studio, type StudioMessage } from '../lib/studio.svelte';
  import Composer from './Composer.svelte';
  import StudioTurn from './StudioTurn.svelte';
  import StudioRequest from './StudioRequest.svelte';
  import CodexLink from './CodexLink.svelte';

  /**
   * Studio (ADR 0016): course work as a Codex chat. `$` suggests skills and `@` the course's files, both left in the
   * text as chips; images and files can be pasted, dropped or chosen; a message sent while Codex works steers it.
   * It is self-contained, so it can sit wherever it is mounted: `active` says it is on screen, and it scrolls whatever
   * scrolls it, keeping its writing box at that container's bottom.
   */
  let { active = true }: { active?: boolean } = $props();

  let busy = $state(false);
  let attaching = $state(0);
  let view: EditorView | undefined;
  let chips: ChipRange[] = [];
  let recalled = 0;
  let list = $state<HTMLElement>();

  $effect(() => {
    if (active) void studio.load();
  });

  const course = $derived(app.libraryCourse?.name ?? app.state?.course?.title ?? '');
  const draftKey = $derived(`studio:${studio.threadId ?? 'new'}`);
  const draft = $derived(app.drafts.get(draftKey));
  const images = $derived(app.drafts.images(draftKey));

  // Course work Studio is for, offered when a chat is empty; each fills the box rather than sending.
  const examples = $derived([
    { label: t('Add files to this course'), text: `$throughline ${t('Add these files to {course}:', { course })} ` },
    { label: t('Check the pages that still need review'), text: `$throughline ${t('Review the pages of {course} that still need checking.', { course })}` },
    { label: t('Change how this course is taught'), text: `$throughline ${t('In {course},', { course })} ` },
  ]);

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
    const key = draftKey;
    const text = draft;
    const attached = images;
    const sent = message(text);
    // The box empties at once, as Codex's does, so the learner can write the next message while this one goes out;
    // a message that fails comes back if the box is still empty.
    busy = true;
    app.drafts.set(key, '');
    app.drafts.setImages(key, []);
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

  /** The nearest ancestor that scrolls: the side panel's body today, the reading column on a page. */
  function scrollParent(node: HTMLElement | undefined) {
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

  const accessLabel = $derived(studio.access?.full_access ? t('Full access') : t('Library access'));
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
        <p class="panel-empty">{t("Ask for course work here: adding files, rebuilding chapters, checking pages, changing how the course is taught. Questions about the material go to Questions.")}</p>
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
      {studio.threadId ? threadLabel(studio.threadId) : t("New chat")}{#if course}{' · '}{course}{/if}
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
    <button
      type="button"
      class="access"
      class:full={studio.access?.full_access}
      title={studio.access?.full_access ? t("Codex can change files anywhere and runs commands without asking.") : t("Codex writes only inside your Throughline folder and asks before anything else.")}
      onclick={() => {
        app.settingsPane = 'teacher';
        app.settingsOpen = true;
      }}
    >{accessLabel}</button>
    {#if studio.context !== null}
      <span class="context" title={t("Share of the model's context this chat uses")}>{t("{percent}% context", { percent: Math.round(studio.context * 100) })}</span>
    {/if}
    {#if attaching}<span class="context" role="status">{t("Attaching…")}</span>{/if}
  {/snippet}
  <div class="panel-foot">
    {#if studio.available !== false}
      <Composer
        id="studio-input"
        value={draft}
        onvalue={(value) => app.drafts.set(draftKey, value)}
        label={t("Message to Codex")}
        placeholder={studio.running ? t("Add to what Codex is doing…") : t("Ask Codex for course work · $ for skills, @ for files")}
        submitLabel={studio.running ? t("Add") : t("Send")}
        disabled={busy || attaching > 0 || studio.available !== true}
        onsubmit={send}
        header={target}
        imagesKey={draftKey}
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
  .transcript {
    gap: 1rem;
  }

  .welcome {
    display: grid;
    gap: 0.6rem;
  }

  .examples {
    display: grid;
    justify-items: start;
    gap: 0.2rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .examples .btn {
    color: var(--accent);
    text-align: left;
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

  .access {
    padding: 0.1rem 0.5rem;
    border: 1px solid var(--rule);
    border-radius: 999px;
    background: none;
    color: var(--pencil);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .access:hover {
    border-color: var(--pencil);
  }

  .access.full {
    border-color: var(--caution);
    color: var(--caution);
  }

  .context {
    font-size: 0.75rem;
    color: var(--pencil);
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
