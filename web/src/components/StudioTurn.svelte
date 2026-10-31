<script lang="ts">
  import { markdown } from '../lib/markdown';
  import { locale, t } from '../lib/i18n.svelte';
  import type { CommandAction, StudioItem, StudioTurn, StudioUserInput } from '../lib/studio.svelte';

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

  const items = $derived(turn.items);
  const answered = $derived(items.some((i) => i.type === 'agentMessage' && (i as { phase: string | null }).phase !== 'commentary' && (i as { text: string }).text));
  const working = $derived(turn.status === 'inProgress');
</script>

<div class="turn">
  {#each items as item (item.id)}
    {#if item.type === 'userMessage'}
      {@const content = (item as Extract<StudioItem, { type: 'userMessage' }>).content}
      <div class="user">
        {#each content as input, i (i)}
          {#if input.type === 'text'}
            <p class="said">{#each segments(input) as part, j (j)}{#if part.chip}<span class="chip">{part.text}</span>{:else}{part.text}{/if}{/each}</p>
          {:else if input.type === 'localImage'}
            <span class="attachment">🖼 {base(input.path)}</span>
          {:else if input.type === 'mention' && !content.some((c) => c.type === 'text' && c.text.includes(input.name))}
            <span class="attachment">@{input.name}</span>
          {/if}
        {/each}
      </div>
    {:else if item.type === 'agentMessage'}
      {@const message = item as Extract<StudioItem, { type: 'agentMessage' }>}
      {#if message.text}
        <div class="prose said-by-codex" class:commentary={message.phase === 'commentary'} use:markdown={{ language: locale.language, text: message.text }}></div>
      {/if}
    {:else if item.type === 'reasoning'}
      {@const summary = ((item as Extract<StudioItem, { type: 'reasoning' }>).summary ?? []).filter(Boolean)}
      {#if summary.length}
        <details class="tool thinking">
          <summary>{t("Thinking")}</summary>
          <div class="prose detail" use:markdown={{ language: locale.language, text: summary.join('\n\n') }}></div>
        </details>
      {/if}
    {:else if item.type === 'commandExecution'}
      {@const command = item as Command}
      <details class="tool" class:failed={failed(command)}>
        <summary>
          <span class="dot" class:running={command.status === 'inProgress'} aria-hidden="true"></span>
          <span class="what">{describe(command)}</span>
          {#if failed(command)}<span class="badge">{command.status === 'declined' ? t("declined") : t("failed")}</span>{/if}
        </summary>
        <pre class="output"><code>$ {inner(command.command)}{command.aggregatedOutput ? '\n' + command.aggregatedOutput : ''}</code></pre>
      </details>
    {:else if item.type === 'fileChange'}
      {@const change = item as Changes}
      <details class="tool" class:failed={change.status === 'failed' || change.status === 'declined'}>
        <summary>
          <span class="dot" class:running={change.status === 'inProgress'} aria-hidden="true"></span>
          <span class="what">{changeSummary(change)}</span>
        </summary>
        {#each change.changes as file (file.path)}
          <p class="file">{file.kind.type === 'add' ? t("New file") : file.kind.type === 'delete' ? t("Deleted") : t("Changed")} · <code>{file.path}</code></p>
          {#if file.diff}<pre class="output diff"><code>{#each file.diff.split('\n') as line, k (k)}<span class={diffClass(line)}>{line}{'\n'}</span>{/each}</code></pre>{/if}
        {/each}
      </details>
    {:else if item.type === 'mcpToolCall'}
      {@const call = item as Extract<StudioItem, { type: 'mcpToolCall' }>}
      <p class="tool line" class:failed={!!call.error}><span class="dot" class:running={call.status === 'inProgress'} aria-hidden="true"></span>{t("Used {tool} from {server}", { tool: call.tool, server: call.server })}</p>
    {:else if item.type === 'webSearch'}
      {@const query = (item as { query?: string }).query}
      <p class="tool line"><span class="dot" aria-hidden="true"></span>{query ? t("Searched the web for {query}", { query }) : t("Searched the web")}</p>
    {:else if item.type === 'imageView'}
      <p class="tool line"><span class="dot" aria-hidden="true"></span>{t("Looked at {file}", { file: base((item as { path: string }).path) })}</p>
    {:else if item.type === 'contextCompaction'}
      <p class="compacted">{t("Earlier messages were summarized to make room")}</p>
    {:else if item.type === 'plan'}
      <div class="prose plan-text" use:markdown={{ language: locale.language, text: (item as { text: string }).text }}></div>
    {/if}
  {/each}

  {#if turn.plan?.length}
    <ol class="plan" aria-label={t("Codex's plan")}>
      {#each turn.plan as step, i (i)}
        <li class={step.status}><span class="box" aria-hidden="true">{step.status === 'completed' ? '✓' : step.status === 'inProgress' ? '•' : ''}</span>{step.step}</li>
      {/each}
    </ol>
  {/if}

  {#if working && last && !answered}
    <p class="working" role="status"><span class="dot running" aria-hidden="true"></span>{t("Working…")}</p>
  {/if}
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

  .thinking summary {
    font-style: italic;
  }

  .detail {
    margin: 0.35rem 0 0 0.9rem;
    font-size: 0.8rem;
    color: var(--pencil);
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

  .output {
    margin: 0.35rem 0 0;
    padding: 0.5rem 0.6rem;
    max-height: 16rem;
    overflow: auto;
    border-radius: var(--radius);
    background: var(--raised);
    border: 1px solid var(--rule);
    font-size: 0.75rem;
    line-height: 1.45;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    color: var(--ink-soft);
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
