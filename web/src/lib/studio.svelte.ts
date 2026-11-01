import { api, ApiError } from './api';
import { t } from './i18n.svelte';

/**
 * Studio (ADR 0016): course work as a Codex chat. The host forwards the App Server's notifications for the threads it
 * has open; this keeps the open thread's turns as Codex sends them and applies those notifications, then reads the
 * thread again when a turn ends, so a dropped event never leaves the transcript out of step.
 *
 * The shapes follow the App Server protocol of the Codex Studio is tested against (`codex app-server generate-ts`);
 * only the fields the interface reads are typed.
 */

export type StudioUserInput =
  | { type: 'text'; text: string; text_elements?: { byteRange: { start: number; end: number }; placeholder: string | null }[] }
  | { type: 'localImage'; path: string }
  | { type: 'image'; url?: string }
  | { type: 'skill'; name: string; path: string }
  | { type: 'mention'; name: string; path: string };

export type CommandAction =
  | { type: 'read'; command: string; name: string; path: string }
  | { type: 'listFiles'; command: string; path: string | null }
  | { type: 'search'; command: string; query: string | null; path: string | null }
  | { type: 'unknown'; command: string };

export type StudioItem =
  | { type: 'userMessage'; id: string; content: StudioUserInput[] }
  | { type: 'agentMessage'; id: string; text: string; phase: 'commentary' | 'partial_answer' | 'final_answer' | null }
  | { type: 'reasoning'; id: string; summary: string[] }
  | { type: 'plan'; id: string; text: string }
  | { type: 'commandExecution'; id: string; command: string; status: string; commandActions: CommandAction[]; aggregatedOutput: string | null; exitCode: number | null }
  | { type: 'fileChange'; id: string; status: string; changes: { path: string; kind: { type: 'add' | 'delete' | 'update' }; diff: string }[] }
  | { type: 'mcpToolCall'; id: string; server: string; tool: string; status: string; error: { message: string } | null }
  | { type: 'webSearch'; id: string; query?: string }
  | { type: 'imageView'; id: string; path: string }
  | { type: 'contextCompaction'; id: string }
  | { type: string; id: string };

export type PlanStep = { step: string; status: 'pending' | 'inProgress' | 'completed' };
export type StudioTurn = {
  id: string;
  status: 'completed' | 'interrupted' | 'failed' | 'inProgress';
  items: StudioItem[];
  error: { message: string } | null;
  plan?: PlanStep[];
};

export type ApprovalMethod = 'item/commandExecution/requestApproval' | 'item/fileChange/requestApproval' | 'item/permissions/requestApproval';
export type UserInputQuestion = { id: string; header: string; question: string; isOther: boolean; isSecret: boolean; options: { label: string; description: string }[] | null };
export type StudioRequest =
  | { id: string; method: ApprovalMethod; params: { threadId: string; turnId: string; reason?: string | null; command?: string | null; cwd?: string | null; grantRoot?: string | null } }
  | { id: string; method: 'item/tool/requestUserInput'; params: { threadId: string; turnId: string; questions: UserInputQuestion[] } };

export type StudioThread = { id: string; name: string; preview: string; updated_at: number | null; running: boolean };
export type StudioSkill = { name: string; path: string; title: string; description: string };
export type StudioFile = { name: string; path: string; absolute: string };
export type StudioAccess = { full_access: boolean; saved: boolean; forced: boolean };
export type StudioEvent = { type: 'studio'; method: string; params: Record<string, any> };

/** What a message sends besides its text: the spans its chips cover (code-point offsets) and what they name. */
export type StudioMessage = {
  text: string;
  elements: { start: number; end: number }[];
  skills: { name: string; path: string }[];
  mentions: { name: string; path: string }[];
  images: string[];
  /** Where a hand-off came from, sent to Codex as context. */
  context?: string;
};

/** Where a hand-off came from: a chapter, section or source location. The chip shows `label`; Codex gets `text`. */
export type StudioOrigin = { label: string; text: string };

/** How Codex marks a hand-off's context in a message (`CONTEXT` in server/studio.py). */
export const CONTEXT = 'Context from Throughline: ';

type History = { id: string; turns: StudioTurn[]; active_turn: string | null; pending: StudioRequest[] };
type Activity = { running: string[]; waiting: StudioRequest[] };

class StudioStore {
  /** Null until asked; false when this Codex cannot run Studio, which then hands off to a Codex chat instead. */
  available = $state<boolean | null>(null);
  error = $state('');
  access = $state<StudioAccess | null>(null);
  threads = $state<StudioThread[]>([]);
  /** The open thread, or null for a new one that starts with the next message. */
  threadId = $state<string | null>(null);
  turns = $state<StudioTurn[]>([]);
  activeTurn = $state<string | null>(null);
  pending = $state<StudioRequest[]>([]);
  /** The course's threads Codex is working in, and what it waits on in any of them, for the top bar. */
  working = $state<string[]>([]);
  waiting = $state<StudioRequest[]>([]);
  /** The hand-off the next message comes from, until it is sent or removed. */
  origin = $state<StudioOrigin | null>(null);
  skills = $state<StudioSkill[]>([]);
  /** Share of the model's context window the thread's last request used. */
  context = $state<number | null>(null);
  loading = $state(false);
  /** Asks for the caret in Studio's box; Studio takes it once it is on screen, however late it mounts. */
  focusRequest = $state(0);
  /** The last request Studio answered; plain, so answering does not rerun what reads it. */
  focusAnswered = 0;
  /** Messages sent in this tab, newest last, which the up arrow brings back into an empty box. */
  sent = $state<string[]>([]);
  #loaded: Promise<void> | null = null;
  #reading = 0;
  /** Reads of a thread still on their way. */
  #readsOut = 0;
  /** Whether the learner chose a chat (sent, opened or started one), which the first load must then leave alone. */
  #chosen = false;

  get running() {
    return !!this.activeTurn;
  }

  get thread() {
    return this.threads.find((t) => t.id === this.threadId);
  }

  /** Loads availability and the course's threads once, opening the most recent thread. */
  load(fresh = false) {
    if (!this.#loaded || fresh) {
      this.#loaded = (async () => {
        this.loading = true;
        try {
          const view = await api.get<{ available: boolean; error?: string; access: StudioAccess; threads: StudioThread[] }>('/api/studio');
          this.available = view.available;
          this.error = view.error ?? '';
          this.access = view.access;
          this.threads = view.threads;
          if (!view.available) return;
          if (!this.#chosen && this.threadId === null && this.turns.length === 0 && view.threads[0]) {
            // Opening the latest chat is a default; once the learner sent, opened or started one, it is theirs.
            this.threadId = view.threads[0].id;
            await this.read(view.threads[0].id);
          }
          if (!this.skills.length) void this.loadSkills();
        } catch (e) {
          this.available = false;
          this.error = e instanceof Error ? e.message : String(e);
        } finally {
          this.loading = false;
        }
      })();
    }
    return this.#loaded;
  }

  async loadSkills() {
    try {
      this.skills = (await api.get<{ skills: StudioSkill[] }>('/api/studio/skills')).skills;
    } catch {
      // Skills are a convenience of the box; Codex still reads `$name` in the text.
    }
  }

  /** What Codex is doing in the course, for the top bar; cheap, so every page asks when a course opens. */
  async loadActivity() {
    try {
      const activity = await api.get<Activity>('/api/studio/activity');
      this.working = activity.running;
      this.waiting = activity.waiting;
    } catch {
      // The events that follow keep it up to date.
    }
  }

  /** A hand-off: a new chat with the request filled in and, when it points somewhere, a chip saying where. */
  handoff(prompt: string, origin: StudioOrigin | null = null) {
    this.newThread();
    this.origin = origin;
    return `${prompt.trim()} `;
  }

  /** The thread to show when the learner follows the top bar's indicator: one Codex waits on, else one it works in. */
  get attention() {
    return this.waiting[0]?.params.threadId ?? this.working[0] ?? null;
  }

  async refreshThreads() {
    try {
      const view = await api.get<{ threads: StudioThread[] }>('/api/studio');
      this.threads = view.threads;
    } catch {
      // The next event or visit tries again.
    }
  }

  async loadAccess() {
    try {
      this.access = await api.get<StudioAccess>('/api/studio/access');
    } catch {
      // Settings shows the switch without the Windows note.
    }
    return this.access;
  }

  async setFullAccess(on: boolean) {
    this.access = await api.put<StudioAccess>('/api/studio/access', { full_access: on });
    return this.access;
  }

  async open(id: string) {
    this.#chosen = true;
    this.threadId = id;
    await this.read(id);
  }

  /** Reads a thread's turns and what Codex is waiting on; a read that a later one (or a send) overtakes is dropped. */
  async read(id: string) {
    const reading = ++this.#reading;
    this.#readsOut++;
    try {
      const history = await api.get<History>(`/api/studio/threads/${encodeURIComponent(id)}`);
      if (reading !== this.#reading || this.threadId !== id) return;
      this.turns = history.turns;
      this.activeTurn = history.active_turn;
      this.pending = history.pending;
      // The host's copy also corrects the top bar for this thread, whose first events may have come before its name.
      this.working = [...this.working.filter((t) => t !== id), ...(history.active_turn ? [id] : [])];
      this.waiting = [...this.waiting.filter((p) => p.params.threadId !== id), ...history.pending];
    } catch (e) {
      if (reading === this.#reading) this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.#readsOut--;
    }
  }

  newThread() {
    this.#chosen = true;
    this.#reading++;
    this.threadId = null;
    this.turns = [];
    this.activeTurn = null;
    this.pending = [];
    this.context = null;
  }

  /** Sends a message: a new turn, or while Codex works, more for the running turn (Codex calls it steering). */
  async send(message: StudioMessage) {
    this.#chosen = true;
    // A read already on its way may describe the thread from before this message: drop it, and read again after.
    const stale = this.#readsOut > 0;
    this.#reading++;
    const origin = this.origin;
    const result = await api.post<{ thread: string; turn: string; steered: boolean }>('/api/studio/messages', {
      thread_id: this.threadId,
      ...message,
      ...(origin ? { context: origin.text } : {}),
    });
    if (this.origin === origin) this.origin = null;
    if (message.text.trim()) this.sent = [...this.sent.filter((s) => s !== message.text), message.text].slice(-50);
    if (this.threadId !== result.thread || stale) {
      // A new thread's first events can arrive before this reply names it, and were not taken for this chat: read it.
      const fresh = this.threadId !== result.thread;
      this.threadId = result.thread;
      void this.read(result.thread);
      if (fresh) void this.refreshThreads();
    }
    if (!result.steered) this.activeTurn = result.turn;
    if (!this.turns.some((turn) => turn.id === result.turn)) {
      this.turns = [...this.turns, { id: result.turn, status: 'inProgress', items: [], error: null }];
    }
    return result;
  }

  async stop() {
    if (!this.threadId) return;
    await api.post(`/api/studio/threads/${encodeURIComponent(this.threadId)}/interrupt`);
  }

  async answer(request: StudioRequest, body: { decision?: string; answers?: Record<string, string[]> }) {
    try {
      await api.post(`/api/studio/requests/${encodeURIComponent(request.id)}`, body);
    } catch (e) {
      // Codex stopped waiting (the turn was stopped, or answered elsewhere): show it as gone.
      if (!(e instanceof ApiError) || e.status !== 404) throw e;
    }
    this.pending = this.pending.filter((p) => p.id !== request.id);
    this.waiting = this.waiting.filter((p) => p.id !== request.id);
  }

  async rename(id: string, name: string) {
    await api.put(`/api/studio/threads/${encodeURIComponent(id)}`, { name });
    await this.refreshThreads();
  }

  async archive(id: string) {
    await api.delete(`/api/studio/threads/${encodeURIComponent(id)}`);
    if (this.threadId === id) this.newThread();
    await this.refreshThreads();
  }

  search(query: string) {
    return api.get<{ files: StudioFile[] }>(`/api/studio/search?q=${encodeURIComponent(query)}`).then((r) => r.files);
  }

  upload(file: File) {
    return api.upload<StudioFile>(`/api/studio/files?name=${encodeURIComponent(file.name)}`, file);
  }

  #turn(id: string) {
    let turn = this.turns.find((x) => x.id === id);
    if (!turn) {
      this.turns.push({ id, status: 'inProgress', items: [], error: null });
      turn = this.turns[this.turns.length - 1];
    }
    return turn;
  }

  #item(turnId: string, itemId: string) {
    return this.turns.find((x) => x.id === turnId)?.items.find((i) => i.id === itemId) as Record<string, any> | undefined;
  }

  apply(event: StudioEvent) {
    const { method, params } = event;
    if (method === 'studio/closed') {
      this.activeTurn = null;
      this.pending = [];
      this.working = [];
      this.waiting = [];
      this.error = t('Codex stopped. Send a message to start it again.');
      return;
    }
    if (method === 'studio/threads') return void this.refreshThreads();
    if (method === 'studio/request') {
      const request = params as StudioRequest;
      if (!this.waiting.some((p) => p.id === request.id)) this.waiting.push(request);
      if (request.params.threadId === this.threadId && !this.pending.some((p) => p.id === request.id)) this.pending.push(request);
      return;
    }
    if (method === 'studio/resolved') {
      this.pending = this.pending.filter((p) => p.id !== params.id);
      this.waiting = this.waiting.filter((p) => p.id !== params.id);
      return;
    }
    const thread = params.threadId ?? params.thread?.id;
    // The top bar follows every thread of the course, not only the open one.
    if (method === 'turn/started' && !this.working.includes(thread)) this.working.push(thread);
    if (method === 'turn/completed') {
      this.working = this.working.filter((t) => t !== thread);
      this.waiting = this.waiting.filter((p) => p.params.turnId !== params.turn.id);
    }
    if (thread !== this.threadId) {
      if (method === 'turn/started' || method === 'turn/completed') void this.refreshThreads();
      return;
    }
    switch (method) {
      case 'turn/started':
        this.#turn(params.turn.id).status = 'inProgress';
        this.activeTurn = params.turn.id;
        this.error = '';
        void this.refreshThreads();
        break;
      case 'turn/completed': {
        const turn = this.#turn(params.turn.id);
        turn.status = params.turn.status;
        turn.error = params.turn.error;
        if (this.activeTurn === params.turn.id) this.activeTurn = null;
        this.pending = this.pending.filter((p) => p.params.turnId !== params.turn.id);
        void this.read(thread);
        void this.refreshThreads();
        break;
      }
      case 'item/started':
      case 'item/completed': {
        const turn = this.#turn(params.turnId);
        const index = turn.items.findIndex((i) => i.id === params.item.id);
        if (index >= 0) {
          // A started message has no text yet; the deltas since then are kept until the completed item replaces them.
          const known = turn.items[index] as Record<string, any>;
          turn.items[index] = method === 'item/started' && known.text ? { ...params.item, text: known.text } : params.item;
        } else {
          turn.items.push(params.item);
        }
        break;
      }
      case 'item/agentMessage/delta':
      case 'item/plan/delta': {
        const item = this.#item(params.turnId, params.itemId);
        if (item) item.text = (item.text ?? '') + params.delta;
        break;
      }
      case 'item/reasoning/summaryPartAdded':
      case 'item/reasoning/summaryTextDelta': {
        const item = this.#item(params.turnId, params.itemId);
        if (!item) break;
        const summary: string[] = (item.summary ??= []);
        while (summary.length <= params.summaryIndex) summary.push('');
        if (params.delta) summary[params.summaryIndex] += params.delta;
        break;
      }
      case 'item/commandExecution/outputDelta': {
        const item = this.#item(params.turnId, params.itemId);
        if (item) item.aggregatedOutput = (item.aggregatedOutput ?? '') + params.delta;
        break;
      }
      case 'turn/plan/updated':
        this.#turn(params.turnId).plan = params.plan;
        break;
      case 'thread/tokenUsage/updated': {
        const usage = params.tokenUsage;
        if (usage?.modelContextWindow) this.context = Math.min(1, usage.last.totalTokens / usage.modelContextWindow);
        break;
      }
      case 'thread/name/updated':
        void this.refreshThreads();
        break;
      case 'error':
        if (!params.willRetry) this.#turn(params.turnId).error = params.error;
        break;
    }
  }
}

export const studio = new StudioStore();
