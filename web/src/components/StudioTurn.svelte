<script lang="ts">
  import { markdown } from '../lib/markdown';
  import StudioQuestions from './StudioQuestions.svelte';
  import { locale, t } from '../lib/i18n.svelte';
  import { CONTEXT, outputTail, parseReply, type CommandAction, type StudioItem, type StudioTurn, type StudioUserInput } from '../lib/studio.svelte';

  /** One Studio turn as Codex draws it: the learner's message, then what Codex said and did, in order. */
  let { turn, last = false }: { turn: StudioTurn; last?: boolean } = $props();

  type Text = Extract<StudioUserInput, { type: 'text' }>;
  type Command = Extract<StudioItem, { type: 'commandExecution' }>;
  type Changes = Extract<StudioItem, { type: 'fileChange' }>;

  /** The text of a message cut at its chips, whose spans Codex counts in UTF-8 bytes. */
  function segments(input: Text) {
    const bytes = new TextEncoder().encode(input.text);
    const decode = (from: number, to: number) => new TextDecoder().decode(bytes.slice(from, to));
    const parts: { text: string; chip: boolean }[] = [];
    let at = 0;
    for (const { byteRange } of [...(input.text_elements ?? [])].sort((a, b) => a.byteRange.start - b.byteRange.start)) {
      if (byteRange.start < at || byteRange.end > bytes.length) continue;
      parts.push({ text: decode(at, byteRange.start), chip: false }, { text: decode(byteRange.start, byteRange.end), chip: true });
      at = byteRange.end;
    }
    parts.push({ text: decode(at, bytes.length), chip: false });
    return parts.filter((p) => p.text);
  }

  const base = (path: string) => path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;

  /** The command a shell wrapper runs (`zsh -lc '…'`), which is what Codex shows. */
  function inner(command: string) {
    const wrapped = command.match(/^\S*(?:bash|zsh|sh|pwsh|powershell)(?:\.exe)?\s+-\w*c\s+(['"]?)([\s\S]*)\1$/);
    return wrapped ? wrapped[2] : command;
  }

  /** What a command did in Codex's own words, from the actions it parsed: Read, Listed, Searched, or Ran. */
  function describe(item: Command) {
    const actions: CommandAction[] = item.commandActions ?? [];
    if (actions.length && actions.every((a) => a.type === 'read')) {
      return t('Read {files}', { files: actions.map((a) => (a.type === 'read' ? a.name || base(a.path) : '')).join(', ') });
    }
    if (actions.length === 1 && actions[0].type === 'listFiles') return t('Listed files in {path}', { path: actions[0].path || '.' });
    if (actions.length === 1 && actions[0].type === 'search') {
      const action = actions[0];
      return action.query ? t('Searched for {query}', { query: action.query }) : t('Searched {path}', { path: action.path || '.' });
    }
    return t('Ran {command}', { command: inner(item.command) });
  }

  const failed = (item: Command) => item.status === 'failed' || item.status === 'declined' || (item.exitCode !== null && item.exitCode !== 0);

  function changeSummary(item: Changes) {
    const paths = item.changes.map((c) => base(c.path));
    return paths.length === 1 ? t('Edited {file}', { file: paths[0] }) : t('Edited {count} files', { count: paths.length });
  }

  const diffClass = (line: string) => (line.startsWith('+') && !line.startsWith('+++') ? 'add' : line.startsWith('-') && !line.startsWith('---') ? 'del' : line.startsWith('@@') ? 'hunk' : '');

  const isTool = (item: StudioItem) => ['commandExecution', 'fileChange', 'mcpToolCall', 'webSearch', 'imageView'].includes(item.type);
  const isMessage = (item: StudioItem): item is Extract<StudioItem, { type: 'agentMessage' }> => item.type === 'agentMessage';
  const running = (item: StudioItem) => (item as { status?: string }).status === 'inProgress';
  /** A command that only looked at files, which Codex counts as exploring. */
  const explores = (item: StudioItem) =>
    item.type === 'commandExecution' && !!(item as Command).commandActions?.length && (item as Command).commandActions.every((a) => a.type !== 'unknown');
  function itemFailed(item: StudioItem) {
    if (item.type === 'commandExecution') return failed(item as Command);
    const status = (item as { status?: string }).status;
    return status === 'failed' || status === 'declined' || (item.type === 'mcpToolCall' && !!(item as { error: unknown }).error);
  }

  /** What one tool call did, in Codex's words. */
  function toolLabel(item: StudioItem) {
    if (item.type === 'commandExecution') return describe(item as Command);
    if (item.type === 'fileChange') return changeSummary(item as Changes);
    if (item.type === 'mcpToolCall') {
      const call = item as Extract<StudioItem, { type: 'mcpToolCall' }>;
      return t('Used {tool} from {server}', { tool: call.tool, server: call.server });
    }
    if (item.type === 'webSearch') {
      const query = (item as { query?: string }).query;
      return query ? t('Searched the web for {query}', { query }) : t('Searched the web');
    }
    return t('Looked at {file}', { file: base((item as { path: string }).path) });
  }

  /** A folded run of tool calls named as Codex names it: what was done, in the order it was first done. */
  function groupLabel(group: StudioItem[]) {
    const counts = new Map<string, number>();
    for (const item of group) {
      const kind = explores(item) ? 'explore' : item.type;
      counts.set(kind, (counts.get(kind) ?? 0) + 1);
    }
    const parts = [...counts].map(([kind, n]) =>
      kind === 'explore' ? t('Explored files')
      : kind === 'commandExecution' ? (n === 1 ? t('Ran a command') : t('Ran commands'))
      : kind === 'fileChange' ? (n === 1 ? t('Edited a file') : t('Edited files'))
      : kind === 'mcpToolCall' ? (n === 1 ? t('Used a tool') : t('Used tools'))
      : kind === 'webSearch' ? t('Searched the web')
      : t('Looked at images'));
    if (locale.language !== 'en') return parts.join('，');
    return parts.map((part, i) => (i ? part[0].toLowerCase() + part.slice(1) : part)).join(', ');
  }

  type Row = { kind: 'item'; item: StudioItem } | { kind: 'tools'; id: string; items: StudioItem[] };

  const working = $derived(turn.status === 'inProgress');
  // The answer is the last message Codex marked final; in a finished turn saved without phases, its last plain message.
  const answer = $derived.by(() => {
    const messages = turn.items.filter(isMessage).filter((m) => m.text || m.questions?.length).reverse();
    return messages.find((m) => m.phase === 'final_answer') ?? (working ? undefined : messages.find((m) => m.phase !== 'commentary'));
  });
  // The learner's message opens the turn; the work follows in order, its consecutive tool calls folded into one row.
  // Reasoning only names what Codex is doing while it works, as in Codex.
  const leading = $derived.by(() => {
    const first = turn.items.findIndex((i) => i.type !== 'userMessage');
    return first < 0 ? turn.items : turn.items.slice(0, first);
  });
  const rows = $derived.by(() => {
    const out: Row[] = [];
    for (const item of turn.items.slice(leading.length)) {
      if (item === answer || item.type === 'reasoning' || (isMessage(item) && !item.text && !item.questions?.length)) continue;
      const previous = out.at(-1);
      if (isTool(item) && previous?.kind === 'tools') previous.items.push(item);
      else if (isTool(item)) out.push({ kind: 'tools', id: item.id, items: [item] });
      else out.push({ kind: 'item', item });
    }
    return out;
  });

  // Once the answer starts, the work before it folds behind how long it took, as Codex folds a turn; the learner can
  // open it again, and their choice holds for this turn.
  const foldable = $derived(!!answer && turn.status !== 'interrupted' && rows.some((r) => r.kind === 'tools' || r.item.type !== 'userMessage'));
  let opened = $state(false);
  const folded = $derived(foldable && !opened);

  let now = $state(Date.now());
  $effect(() => {
    if (!working) return;
    const clock = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(clock);
  });
  function duration(ms: number) {
    const seconds = Math.max(1, Math.round(ms / 1000));
    const minutes = Math.floor(seconds / 60);
    return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
  }
  const took = $derived(
    turn.durationMs ? turn.durationMs
    : turn.startedAt && turn.completedAt ? (turn.completedAt - turn.startedAt) * 1000
    : turn.startedAt && working ? now - turn.startedAt * 1000
    : null,
  );
  const steps = $derived(rows.reduce((n, r) => n + (r.kind === 'tools' ? r.items.length : 1), 0));
  const foldLabel = $derived(
    took === null ? t('Worked through {count} steps', { count: steps })
    : working ? t('Working for {time}', { time: duration(took) })
    : t('Worked for {time}', { time: duration(took) }),
  );

  // While Codex works, the heading of its newest reasoning says what it is thinking about, as Codex shows it.
  const thinking = $derived.by(() => {
    const summary = ([...turn.items].reverse().find((i) => i.type === 'reasoning') as Extract<StudioItem, { type: 'reasoning' }> | undefined)?.summary ?? [];
    const text = summary.filter(Boolean).at(-1) ?? '';
    const heading = [...text.matchAll(/\*\*([^*\n]+)\*\*|^#+\s+(.+)$/gm)].at(-1);
    return heading ? (heading[1] ?? heading[2]).trim() : '';
  });

  // Output is drawn only while its fold is open, so a long run costs nothing until the learner looks at it.
  let shown = $state<Record<string, boolean>>({});
  const toggle = (id: string) => (event: Event) => (shown[id] = (event.currentTarget as HTMLDetailsElement).open);
</script>

{#snippet said(item: StudioItem)}
  {@const content = (item as Extract<StudioItem, { type: 'userMessage' }>).content}
  <div class="user">
    {#each content as input, i (i)}
      {#if input.type === 'text' && input.text.startsWith(CONTEXT)}
        <span class="origin" title={input.text.slice(CONTEXT.length)}>{input.text.slice(CONTEXT.length)}</span>
      {:else if input.type === 'text' && parseReply(input.text)}
        <!-- Answers to Codex's questions, sent in the form Codex reads, shown as what the learner answered. -->
        <dl class="replies">
          {#each parseReply(input.text) ?? [] as reply (reply.questionItemId)}<dt>{reply.question}</dt><dd>{reply.answer}</dd>{/each}
        </dl>
      {:else if input.type === 'text'}
        <p class="said">{#each segments(input) as part, j (j)}{#if part.chip}<span class="chip">{part.text}</span>{:else}{part.text}{/if}{/each}</p>
      {:else if input.type === 'localImage'}
        <span class="attachment">🖼 {base(input.path)}</span>
      {:else if input.type === 'mention' && !content.some((c) => c.type === 'text' && c.text.includes(input.name))}
        <span class="attachment">@{input.name}</span>
      {/if}
    {/each}
  </div>
{/snippet}

{#snippet tool(item: StudioItem)}
  {#if item.type === 'commandExecution'}
    {@const command = item as Command}
    <details class="tool" class:failed={failed(command)} ontoggle={toggle(item.id)}>
      <summary>
        <span class="dot" class:running={command.status === 'inProgress'} aria-hidden="true"></span>
        <span class="what">{describe(command)}</span>
        {#if failed(command)}<span class="badge">{command.status === 'declined' ? t("declined") : t("failed")}</span>{/if}
      </summary>
      {#if shown[item.id]}
        <div class="output"><pre><code>$ {inner(command.command)}{command.aggregatedOutput ? '\n' + outputTail(command.aggregatedOutput) : ''}</code></pre></div>
      {/if}
    </details>
  {:else if item.type === 'fileChange'}
    {@const change = item as Changes}
    <details class="tool" class:failed={itemFailed(change)} ontoggle={toggle(item.id)}>
      <summary>
        <span class="dot" class:running={change.status === 'inProgress'} aria-hidden="true"></span>
        <span class="what">{changeSummary(change)}</span>
      </summary>
      {#if shown[item.id]}
        {#each change.changes as file (file.path)}
          <p class="file">{file.kind.type === 'add' ? t("New file") : file.kind.type === 'delete' ? t("Deleted") : t("Changed")} · <code>{file.path}</code></p>
          {#if file.diff}<div class="output diff"><pre><code>{#each file.diff.split('\n') as line, k (k)}<span class={diffClass(line)}>{line}{'\n'}</span>{/each}</code></pre></div>{/if}
        {/each}
      {/if}
    </details>
  {:else}
    <p class="tool line" class:failed={itemFailed(item)}><span class="dot" class:running={running(item)} aria-hidden="true"></span><span class="what">{toolLabel(item)}</span></p>
  {/if}
{/snippet}

{#snippet message(item: Extract<StudioItem, { type: 'agentMessage' }>)}
  {#if item.text}
    <div class="prose said-by-codex" class:commentary={item.phase === 'commentary' && item !== answer} use:markdown={{ language: locale.language, text: item.text }}></div>
  {/if}
  {#if item.questions?.length}
    <StudioQuestions item={item.id} questions={item.questions} current={last} />
  {/if}
{/snippet}

{#snippet work(row: Row, live: boolean)}
  {#if row.kind === 'tools' && row.items.length === 1}
    {@render tool(row.items[0])}
  {:else if row.kind === 'tools'}
    {@const current = row.items.at(-1)!}
    <!-- Consecutive tool calls fold into one row; while Codex is still at them, the row names what it is doing now. -->
    <details class="tool group" class:failed={row.items.some(itemFailed)}>
      <summary>
        <span class="dot" class:running={live && running(current)} aria-hidden="true"></span>
        <span class="what">{live ? toolLabel(current) : groupLabel(row.items)}</span>
        <span class="count">{row.items.length}</span>
      </summary>
      <div class="calls">
        {#each row.items as item (item.id)}{@render tool(item)}{/each}
      </div>
    </details>
  {:else if row.item.type === 'userMessage'}
    {@render said(row.item)}
  {:else if isMessage(row.item)}
    {@render message(row.item)}
  {:else if row.item.type === 'contextCompaction'}
    <p class="compacted">{t("Earlier messages were summarized to make room")}</p>
  {:else if row.item.type === 'plan'}
    <div class="prose plan-text" use:markdown={{ language: locale.language, text: (row.item as { text: string }).text }}></div>
  {/if}
{/snippet}

<div class="turn">
  {#each leading as item (item.id)}{@render said(item)}{/each}

  {#if foldable}
    <button type="button" class="fold" aria-expanded={!folded} onclick={() => (opened = folded)}>
      <span class="chevron" class:open={!folded} aria-hidden="true"></span>{foldLabel}
    </button>
  {/if}
  {#each rows as row, i (row.kind === 'tools' ? row.id : row.item.id)}
    {#if !folded}
      {@render work(row, working && !answer && last && i === rows.length - 1)}
    {:else if row.kind === 'item' && row.item.type === 'userMessage'}
      <!-- What the learner added while Codex worked stays in view when the work folds, as in Codex. -->
      {@render said(row.item)}
    {/if}
  {/each}

  {#if turn.plan?.length && !folded}
    <ol class="plan" aria-label={t("Codex's plan")}>
      {#each turn.plan as step, i (i)}
        <li class={step.status}><span class="box" aria-hidden="true">{step.status === 'completed' ? '✓' : step.status === 'inProgress' ? '•' : ''}</span>{step.step}</li>
      {/each}
    </ol>
  {/if}

  {#if working && last && !answer}
    <p class="working" role="status"><span class="dot running" aria-hidden="true"></span>{thinking || t("Working…")}</p>
  {/if}
  {#if answer}{@render message(answer)}{/if}
  {#if turn.status === 'interrupted'}
    <p class="ended">{t("Stopped")}</p>
  {:else if turn.status === 'failed' || turn.error}
    <p class="ended error" role="alert">{turn.error?.message || t("Codex could not finish this.")}</p>
  {/if}
</div>

<style>
  .turn {
    display: grid;
    gap: 0.55rem;
    min-width: 0;
  }

  .user {
    justify-self: end;
    display: grid;
    gap: 0.3rem;
    max-width: 92%;
    padding: 0.5rem 0.75rem;
    border-radius: calc(var(--radius) * 2);
    background: var(--accent-wash);
    color: var(--ink);
    font-size: var(--step--1);
  }

  .said {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .replies {
    display: grid;
    gap: 0.15rem;
    margin: 0;
  }

  .replies dt {
    color: var(--ink-soft);
  }

  .replies dd {
    margin: 0 0 0.25rem;
    font-weight: 600;
  }

  .chip {
    padding: 0.02rem 0.3rem;
    border-radius: 5px;
    background: var(--raised);
    color: var(--accent);
    font-family: var(--mono);
    font-size: 0.92em;
  }

  .attachment {
    justify-self: end;
    font-size: 0.8rem;
    color: var(--ink-soft);
  }

  /* Where a hand-off came from, sent with the message. */
  .origin {
    justify-self: end;
    max-width: 100%;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-size: 0.75rem;
    color: var(--accent);
  }

  .said-by-codex {
    font-size: var(--step--1);
    overflow-wrap: anywhere;
  }

  .commentary {
    color: var(--pencil);
  }

  .tool {
    min-width: 0;
    font-size: 0.8rem;
    color: var(--pencil);
  }

  .tool summary,
  .tool.line {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    min-width: 0;
    margin: 0;
    cursor: pointer;
    list-style: none;
  }

  .tool.line {
    cursor: default;
  }

  .tool summary::-webkit-details-marker {
    display: none;
  }

  .tool summary:hover .what {
    color: var(--ink-soft);
  }

  .what {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-family: var(--mono);
  }

  .count {
    flex: none;
    padding: 0 0.35rem;
    border-radius: 999px;
    background: var(--raised);
    font-size: 0.7rem;
  }

  /* An opened run of tool calls scrolls in a box of its own, so a long run never pushes the answer far away. */
  .calls {
    display: grid;
    gap: 0.4rem;
    max-height: 14rem;
    overflow-y: auto;
    overscroll-behavior: contain;
    margin: 0.4rem 0 0 0.2rem;
    padding-left: 0.7rem;
    border-left: 1px solid var(--rule);
  }

  /* The work of a turn with an answer, folded behind how long it took. */
  .fold {
    justify-self: start;
    display: inline-flex;
    align-items: center;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-size: 0.8rem;
    color: var(--pencil);
    cursor: pointer;
  }

  .fold:hover {
    color: var(--ink-soft);
  }

  .dot {
    flex: none;
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: var(--rule-strong);
    transform: translateY(-0.05rem);
  }

  .dot.running {
    background: var(--accent);
    animation: pulse 1.2s ease-in-out infinite;
  }

  .failed .dot {
    background: var(--danger);
  }

  .badge {
    flex: none;
    color: var(--danger);
  }

  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }

  /* Reversed, so a long output opens at its end, which is what the learner looks for, as in Codex. */
  .output {
    display: flex;
    flex-direction: column-reverse;
    margin: 0.35rem 0 0;
    padding: 0.5rem 0.6rem;
    max-height: 16rem;
    overflow: auto;
    overscroll-behavior: contain;
    border-radius: var(--radius);
    background: var(--raised);
    border: 1px solid var(--rule);
    font-size: 0.75rem;
    line-height: 1.45;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--ink-soft);
  }

  .output pre {
    margin: 0;
    font: inherit;
    white-space: inherit;
  }

  .diff .add {
    color: var(--success, #2f7d4f);
  }

  .diff .del {
    color: var(--danger);
  }

  .diff .hunk {
    color: var(--pencil);
  }

  .file {
    margin: 0.4rem 0 0;
    overflow-wrap: anywhere;
  }

  .compacted {
    margin: 0;
    text-align: center;
    font-size: 0.75rem;
    color: var(--pencil);
  }

  .plan {
    display: grid;
    gap: 0.2rem;
    margin: 0;
    padding: 0.5rem 0.65rem;
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    list-style: none;
    font-size: 0.8rem;
    color: var(--ink-soft);
  }

  .plan li {
    display: flex;
    gap: 0.45rem;
  }

  .plan .completed {
    color: var(--pencil);
    text-decoration: line-through;
  }

  .plan .inProgress {
    color: var(--ink);
    font-weight: 600;
  }

  .box {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: 0.95rem;
    height: 0.95rem;
    border: 1px solid var(--rule-strong);
    border-radius: 3px;
    font-size: 0.65rem;
    text-decoration: none;
  }

  .working,
  .ended {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
    margin: 0;
    font-size: 0.8rem;
    color: var(--pencil);
  }

  .ended.error {
    color: var(--danger);
  }

  .plan-text {
    font-size: var(--step--1);
  }
</style>
