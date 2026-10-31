import { tick } from 'svelte';
import { locale, t, type Language } from './i18n.svelte';
import { api, ApiError, newId } from './api';
import { locate, occurrences } from './highlight';
import { scrollStage, stageHeight, stageOffset, stageScroll } from './stage';
import type { Annotation, AnnotationSource, ChangeScope, Channel, Chapter, CheckChoice, ChapterBuild, DeltaEvent, HostEvent, Library, MemoryEntry, Preferences, Question, Ref, Settings, SourceView, State, Task, Turn, UpdateCheck } from './types';

export type PanelTab = 'questions' | 'source' | 'notes' | 'memory';
export type Connection = 'connecting' | 'live' | 'reconnecting';
export type Quote = { text: string; turnId: string | null; scrollY: number; source?: string; questionId?: string };

const DEFAULT_PANEL = 400;

/** Parts of the state the host loads alone (`state.ALONE`), and the change scopes that need only that part. */
type StatePart = 'preparation' | 'settings' | 'builds' | 'memory';
const ALONE: Partial<Record<ChangeScope, StatePart>> = { preparation: 'preparation', settings: 'settings', builds: 'builds', memory: 'memory' };
/** Channels of work the host does on its own, as BACKGROUND in guided_learning/streaming.py. */
const BACKGROUND: Channel[] = ['preparation', 'build', 'consolidation'];

/** Each course owns its language; the last one used also labels the library before a course opens. */
function rememberLanguage(language?: Language): Language | null {
  try {
    if (language) localStorage.setItem('language', language);
    const stored = localStorage.getItem('language');
    return stored === 'en' || stored === 'zh-CN' ? stored : null;
  } catch {
    return null;
  }
}

function drop(annotations: Annotation[], id: string) {
  const index = annotations.findIndex((a) => a.id === id);
  if (index >= 0) annotations.splice(index, 1);
}

function storedFold() {
  try {
    return localStorage.getItem('route-folded') === 'yes';
  } catch {
    return false;
  }
}

function storedWidth() {
  try {
    return Number(localStorage.getItem('panel-width')) || DEFAULT_PANEL;
  } catch {
    return DEFAULT_PANEL;
  }
}

/**
 * Unsent text the learner typed (exercise answers, lesson requests, follow-ups), keyed by what it belongs to, so it
 * survives moving between sections and reloads within the tab.
 */
class Drafts {
  #values = $state<Record<string, string>>(readDrafts());

  get(key: string): string {
    return this.#values[key] ?? '';
  }

  /** The images attached to a draft, by name; kept beside its text under `images:<key>`. */
  images(key: string): string[] {
    try {
      const names = JSON.parse(this.get(`images:${key}`) || '[]');
      return Array.isArray(names) ? names : [];
    } catch {
      return [];
    }
  }

  setImages(key: string, names: string[]) {
    this.set(`images:${key}`, names.length ? JSON.stringify(names) : '');
  }

  set(key: string, value: string) {
    if (value === this.get(key)) return;
    if (value) this.#values[key] = value;
    else delete this.#values[key];
    try {
      sessionStorage.setItem('drafts', JSON.stringify(this.#values));
    } catch {
      // The draft still lives for this page.
    }
  }
}

function readDrafts(): Record<string, string> {
  try {
    const stored = JSON.parse(sessionStorage.getItem('drafts') ?? '{}');
    return stored && typeof stored === 'object' ? stored : {};
  } catch {
    return {};
  }
}

class AppStore {
  state = $state<State | null>(null);
  connection = $state<Connection>('connecting');
  error = $state<string | null>(null);
  library = $state<Library | null>(null);
  libraryOpen = $state(false);
  /** Teacher settings belong to the learner, so they are available before a course is open. */
  settings = $state<Settings | null>(null);
  /** The latest update check; stays null when GitHub cannot be reached, so a failed launch check shows nothing. */
  update = $state<UpdateCheck | null>(null);
  #settingsWrites = 0;

  /** Concept shown in the reading column; null follows the formal position. */
  viewing = $state<string | null>(null);
  /** Chapter whose page replaces the section in the reading column. */
  viewingChapter = $state<string | null>(null);
  /** The review page replaces the reading column (ADR 0008). */
  reviewOpen = $state(false);

  panelOpen = $state(false);
  panelTab = $state<PanelTab>('questions');
  source = $state<SourceView | null>(null);
  sourceLoading = $state(false);
  /** The Source tab shows every course document instead of the open one. */
  sourceList = $state(false);
  quote = $state<Quote | null>(null);
  settingsOpen = $state(false);
  /** The Settings category to show when the dialog next opens, such as About from the update notice. */
  settingsPane = $state<string | null>(null);
  routeOpen = $state(false);
  /** The learner folded the route to its capsule; a stage too narrow for it folds it regardless. */
  routeFolded = $state(storedFold());
  /** Set by the app: the reading column has no room beside the full route, and the window is a phone's. */
  stageNarrow = $state(false);
  phone = $state(false);
  shortcutsOpen = $state(false);
  /** Question thread to scroll to and flash in the side panel. */
  focusThread = $state<string | null>(null);
  /** Annotation to scroll to and flash in the Notes tab. */
  focusAnnotation = $state<string | null>(null);
  panelWidth = $state(storedWidth());
  #widthChosen = storedWidth() !== DEFAULT_PANEL;
  #sources = new Map<string, Promise<SourceView>>();
  /** Only the newest source request may update the reader. */
  #sourceRequest = 0;
  readonly drafts = new Drafts();

  #refreshTimer: ReturnType<typeof setTimeout> | null = null;
  #refreshing: Promise<void> | null = null;
  /** What the next load fetches: the whole state, some parts of it, or nothing (null). */
  #queued: Set<StatePart> | 'all' | null = null;
  /** Deltas that arrive while a state snapshot is in flight; replayed onto the snapshot so no text is lost. */
  #inflight: DeltaEvent[] | null = null;
  /** Annotation changes shown before the host confirms them; reapplied to any snapshot loaded meanwhile. */
  #pending = new Map<string, (annotations: Annotation[]) => void>();
  /** Chapters the learner opened or closed in the route, and the chapter in view when they did. */
  #chapterToggles = $state<{ at: string | null; open: Record<string, boolean> }>({ at: null, open: {} });

  get currentId(): string | null {
    const s = this.state;
    return s?.position?.concept_id ?? s?.curriculum.route[0] ?? null;
  }

  /** The open course as the library lists it; its folder name is how Codex requests name the course. */
  get libraryCourse() {
    const library = this.library;
    return library?.root ? library.courses.find((c) => c.path === library.active) : undefined;
  }

  get viewingId(): string | null {
    return this.viewing ?? this.currentId;
  }

  concept(id: string | null | undefined) {
    return this.state?.curriculum.concepts.find((c) => c.id === id);
  }

  get chapters(): Chapter[] {
    return this.state?.curriculum.chapters ?? [];
  }

  chapterOf(conceptId: string | null | undefined): Chapter | undefined {
    return this.chapters.find((c) => conceptId && c.concept_ids.includes(conceptId));
  }

  /** The chapter of what the reading column shows: a chapter page, else the section in view. */
  get chapterInView(): string | null {
    return this.viewingChapter ?? this.chapterOf(this.viewingId)?.id ?? null;
  }

  /**
   * Whether a chapter shows its sections in the route, folded or not: the chapter in view, or the chapter being studied
   * while the one in view has no sections yet, unless the learner opened or closed chapters since. Their choice lasts
   * until the chapter in view changes or they pick something to read.
   */
  chapterOpen(chapterId: string) {
    const toggles = this.#chapterToggles.at === this.chapterInView ? this.#chapterToggles.open : {};
    const inView = this.chapters.find((c) => c.id === this.chapterInView);
    return toggles[chapterId] ?? chapterId === (inView?.concept_ids.length ? inView.id : this.chapterOf(this.currentId)?.id);
  }

  toggleChapter(chapterId: string) {
    const at = this.chapterInView;
    const open = this.#chapterToggles.at === at ? this.#chapterToggles.open : {};
    this.#chapterToggles = { at, open: { ...open, [chapterId]: !this.chapterOpen(chapterId) } };
  }

  buildOf(chapterId: string | null | undefined): ChapterBuild | undefined {
    return (this.state?.builds ?? []).find((b) => b.chapter_id === chapterId);
  }

  /** The chapter the app is building or about to build; only one builds at a time. */
  get activeBuild(): ChapterBuild | undefined {
    return (this.state?.builds ?? []).find((b) => b.status === 'queued' || b.status === 'building');
  }

  isSkipped(conceptId: string | null | undefined) {
    return (this.state?.skipped ?? []).some((s) => s.concept_id === conceptId);
  }

  routeIndex(id: string | null | undefined) {
    return id ? (this.state?.curriculum.route.indexOf(id) ?? -1) : -1;
  }

  /** A section's own lessons; a chapter recap anchored to it belongs to the chapter page instead. */
  lessons(conceptId: string | null): Turn[] {
    return (this.state?.turns ?? []).filter((t) => t.channel === 'mainline' && t.concept_id === conceptId && !t.chapter_id);
  }

  recaps(chapterId: string | null | undefined): Turn[] {
    return (this.state?.turns ?? []).filter((t) => t.channel === 'mainline' && !!chapterId && t.chapter_id === chapterId);
  }

  /** Whether any section of the chapter has a completed lesson, which a recap and the chapter quiz need. */
  chapterStudied(chapterId: string | null | undefined) {
    const ids = this.chapters.find((c) => c.id === chapterId)?.concept_ids ?? [];
    return ids.some((id) => this.lessons(id).some((t) => t.status === 'completed'));
  }

  /** The chapter owning a lesson or exercise an annotation or question points at, when it is a recap or quiz question. */
  ownerChapter(item: { turn_id?: string | null; task_id?: string | null }): string | undefined {
    if (item.turn_id) return this.turn(item.turn_id)?.chapter_id;
    if (item.task_id) return this.state?.practice.tasks.find((t) => t.id === item.task_id)?.chapter_id;
    return undefined;
  }

  turn(id: string | null | undefined) {
    return this.state?.turns.find((t) => t.id === id);
  }

  /** The stepped lesson a turn teaches a step of, with the step's number; null for a single-reply lesson. */
  stepOf(turnId: string) {
    for (const lesson of this.state?.lessons ?? []) {
      const index = lesson.steps.findIndex((s) => s.turn_id === turnId);
      if (index >= 0) return { lesson, number: index + 1 };
    }
    return null;
  }

  /** The section's stepped lesson that still has steps to teach, once its first step has started. */
  openLesson(conceptId: string | null) {
    return (this.state?.lessons ?? []).find(
      (l) => l.concept_id === conceptId && !!this.turn(l.steps[0]?.turn_id) && l.steps.some((s) => !s.turn_id),
    );
  }

  hasLesson(conceptId: string | null) {
    return this.lessons(conceptId).some((t) => t.status === 'completed' || t.status === 'running');
  }

  /** Whether the section's lesson is finished: one completed, none being written, and no planned step left to teach. */
  studied(conceptId: string | null) {
    const lessons = this.lessons(conceptId);
    return lessons.some((t) => t.status === 'completed') && !lessons.some((t) => t.status === 'running') && !this.openLesson(conceptId);
  }

  /** How far an unfinished stepped lesson has come: the steps taught so far, of those planned now. */
  stepProgress(conceptId: string | null) {
    const lesson = this.openLesson(conceptId);
    return lesson ? { number: lesson.steps.filter((s) => s.turn_id).length, total: lesson.steps.length } : null;
  }

  get runningLesson() {
    return this.state?.turns.find((t) => t.channel === 'mainline' && t.status === 'running') ?? null;
  }

  isRunning(turnId: string | null | undefined) {
    return this.turn(turnId)?.status === 'running';
  }

  /** Loads the course state, or only `parts` of it; sync() is the entry point, so two loads never race. */
  async #load(parts: StatePart[] | null): Promise<void> {
    // Settings saved here while a load was in flight are newer than what it fetched; the next load brings them.
    const written = this.#settingsWrites;
    const take = (settings: Settings | undefined) => {
      if (settings && written === this.#settingsWrites) this.settings = settings;
    };
    if (parts && this.state) {
      try {
        const partial = await api.get<Partial<State>>(`/api/state?only=${parts.join(',')}`);
        if (this.state) Object.assign(this.state, partial);
        take(partial.settings);
      } catch (e) {
        // A course closed meanwhile needs the whole state, which also reports why.
        if (e instanceof ApiError && e.code === 'no_course') return this.#load(null);
        this.error = (e as Error).message;
      }
      return;
    }
    this.#inflight = [];
    try {
      const state = await api.get<State>('/api/state');
      const missed = this.#inflight;
      this.state = state;
      for (const delta of missed) this.#delta(delta);
      for (const change of this.#pending.values()) change(this.state.annotations);
      take(this.state.settings);
      locale.language = this.state.preferences.language;
      rememberLanguage(locale.language);
      this.error = null;
      if (!this.library) void this.loadLibrary(true);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'no_course') {
        this.state = null;
        this.libraryOpen = true;
        locale.language = rememberLanguage() ?? locale.language;
        try {
          const [settings] = await Promise.all([api.get<Settings>('/api/settings'), this.loadLibrary()]);
          take(settings);
        } catch (error) {
          this.error = (error as Error).message;
        }
      } else this.error = (e as Error).message;
    } finally {
      this.#inflight = null;
    }
  }

  /** While a course is open the library only feeds its Codex links, so a failure there stays quiet. */
  async loadLibrary(quiet = false) {
    try {
      this.library = await api.get<Library>('/api/library');
    } catch (e) {
      if (!quiet) this.error = (e as Error).message;
    }
  }

  showLibrary() {
    this.libraryOpen = true;
    void this.loadLibrary();
  }

  async openCourse(name: string) {
    const opened = await this.act(() => api.post<Library>('/api/library/open', { name }));
    // Everything in the store belongs to one course, so start clean.
    if (opened) location.reload();
  }

  /** Reloads the state shortly, so a burst of changes costs one load; a load that starts meanwhile covers them. */
  refresh(parts: StatePart[] | 'all' = 'all') {
    this.#queue(parts);
    if (this.#refreshTimer) return;
    this.#refreshTimer = setTimeout(() => {
      this.#refreshTimer = null;
      if (this.#queued) void this.#drain();
    }, 120);
  }

  /**
   * Reloads the state (or `parts` of it), one load at a time. A request made while a load runs joins the one load
   * queued after it, and the returned promise settles once the state reflects everything requested so far.
   */
  sync(parts: StatePart[] | 'all' = 'all'): Promise<void> {
    this.#queue(parts);
    return this.#drain();
  }

  #queue(parts: StatePart[] | 'all') {
    this.#queued = parts === 'all' || this.#queued === 'all' ? 'all' : new Set([...(this.#queued ?? []), ...parts]);
  }

  #drain(): Promise<void> {
    if (this.#refreshing) return this.#refreshing;
    this.#refreshing = (async () => {
      try {
        while (this.#queued) {
          const parts = this.#queued;
          this.#queued = null;
          await this.#load(parts === 'all' ? null : [...parts]);
        }
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.#refreshing = null;
      }
    })();
    return this.#refreshing;
  }

  /** Asks the host whether a newer Throughline is out; `fresh` skips the version the host found earlier. */
  async checkForUpdate(fresh = false) {
    this.update = await api.get<UpdateCheck>(fresh ? '/api/update?fresh=1' : '/api/update');
    return this.update;
  }

  connect() {
    const events = new EventSource('/api/events');
    events.onopen = () => {
      // Anything may have changed while disconnected.
      if (this.connection !== 'connecting') void this.sync();
      this.connection = 'live';
    };
    events.onerror = () => {
      this.connection = 'reconnecting';
    };
    events.onmessage = (message) => this.#apply(JSON.parse(message.data) as HostEvent);
  }

  #apply(event: HostEvent) {
    if (event.type === 'changed' && event.scope === 'course') {
      location.reload();
      return;
    }
    if (event.type === 'changed' && event.scope === 'library') {
      if (this.libraryOpen || this.library) void this.loadLibrary(!this.libraryOpen);
      return;
    }
    if (event.type === 'delta') this.#inflight?.push(event);
    const turns = this.state?.turns;
    if (!turns) {
      if (event.type === 'changed') this.refresh();
      return;
    }
    if (event.type === 'delta') {
      this.#delta(event);
    } else if (event.type === 'turn') {
      const index = turns.findIndex((t) => t.id === event.turn.id);
      if (index >= 0) turns[index] = event.turn;
      else turns.push(event.turn);
      // A finished background turn is followed by a change event naming what else it changed.
      if (event.turn.status !== 'running' && !BACKGROUND.includes(event.turn.channel)) this.refresh();
    } else {
      const part = ALONE[event.scope];
      this.refresh(part ? [part] : 'all');
    }
  }

  /** Appends streamed text only when it is the turn's next event; anything else means this copy is out of step. */
  #delta(event: DeltaEvent) {
    const turn = this.state?.turns.find((t) => t.id === event.id);
    if (turn && event.attempt < turn.attempt) return;
    if (!turn || turn.attempt !== event.attempt || turn.status !== 'running') return this.refresh();
    if (event.sequence <= turn.sequence) return; // already part of this copy
    if (event.sequence !== turn.sequence + 1) return this.refresh();
    turn.text += event.text;
    turn.sequence = event.sequence;
  }

  /**
   * Runs an action, reporting failures in the shared error banner. Returns undefined on failure. On success it
   * resolves once the state shows the action's effect, so a caller that stays busy until then cannot submit twice.
   */
  async act<T>(action: () => Promise<T>): Promise<T | undefined> {
    this.error = null;
    try {
      const result = await action();
      await this.sync();
      return result;
    } catch (e) {
      this.error = e instanceof ApiError || e instanceof Error ? e.message : String(e);
      return undefined;
    }
  }

  view(conceptId: string) {
    this.viewingChapter = null;
    this.reviewOpen = false;
    this.viewing = conceptId === this.currentId ? null : conceptId;
    this.routeOpen = false;
    this.#chapterToggles = { at: null, open: {} };
    scrollStage(0);
  }

  /**
   * Once the reading column has re-rendered, scrolls to a passage in a lesson, else to `fallback` (a page offset),
   * else to the lesson itself. `occurrence`, or else `near`, picks between repeats of the passage.
   */
  async #scrollToLesson(
    turnId: string | null | undefined,
    passage: string | null | undefined,
    options: { near?: number; fallback?: number; occurrence?: number } = {},
  ) {
    await tick();
    requestAnimationFrame(() => {
      const lesson = turnId ? document.getElementById(`turn-${turnId}`) : null;
      const body = lesson?.querySelector<HTMLElement>('.lesson-body');
      const range = !body || !passage ? null
        : options.occurrence !== undefined ? (occurrences(body, passage)[options.occurrence] ?? locate(body, passage))
        : locate(body, passage, options.near);
      let top: number | null = null;
      if (range) top = stageOffset(range.getBoundingClientRect().top) - stageHeight() / 3;
      else if (options.fallback !== undefined) top = options.fallback;
      else if (lesson) top = stageOffset(lesson.getBoundingClientRect().top) - 24;
      if (top !== null) scrollStage(Math.max(0, top));
    });
  }

  /** Brings the reading column back to the passage a question was about, falling back to where the learner was reading. */
  returnTo(question: Question) {
    const turnId = question.selected_turn_id ?? question.main_turn_id;
    const chapter = this.ownerChapter({ turn_id: turnId });
    if (chapter) {
      this.viewChapter(chapter);
      return this.#scrollToLesson(turnId, question.selection);
    }
    if (this.currentId) this.view(this.currentId);
    const sameSection = question.anchor?.concept_id === this.currentId && question.anchor.scroll_y != null;
    return this.#scrollToLesson(turnId, question.selection, {
      near: sameSection ? question.anchor.scroll_y! + stageHeight() / 2 : undefined,
      fallback: sameSection ? question.anchor.scroll_y! : undefined,
    });
  }

  explanationsFor(conceptId: string | null) {
    return (this.state?.deferred_explanations ?? []).filter((e) => e.target_concept_id === conceptId);
  }

  annotationsFor(conceptId: string | null): Annotation[] {
    return (this.state?.annotations ?? []).filter((a) => a.concept_id === conceptId);
  }

  bookmark(conceptId: string | null, source?: AnnotationSource | null): Annotation | undefined {
    return this.annotationsFor(conceptId).find(
      (a) =>
        a.kind === 'bookmark' &&
        (source ? a.source?.source_id === source.source_id && a.source.revision === source.revision && a.source.unit_id === source.unit_id : !a.source),
    );
  }

  /**
   * Shows an annotation change at once instead of after a full state reload, which grows with the course. The change
   * stays applied until the host answers; a failure takes it back and reports the error. The host's change event
   * reloads the state afterwards as usual.
   */
  async #annotation<T>(change: (annotations: Annotation[]) => void, request: () => Promise<T>, settle?: (result: T) => void): Promise<T | undefined> {
    const key = newId();
    this.error = null;
    this.#pending.set(key, change);
    if (this.state) change(this.state.annotations);
    try {
      const result = await request();
      this.#pending.delete(key);
      settle?.(result);
      return result;
    } catch (e) {
      this.#pending.delete(key);
      this.error = e instanceof Error ? e.message : String(e);
      await this.sync();
      return undefined;
    }
  }

  annotate(annotation: Pick<Annotation, 'kind' | 'concept_id'> & Partial<Pick<Annotation, 'passage' | 'occurrence' | 'note' | 'images' | 'turn_id' | 'task_id' | 'source'>>) {
    const now = Date.now() / 1000;
    // Choosing the ID here keeps the shown annotation the same item once the host has saved it.
    const draft: Annotation = {
      turn_id: null, task_id: null, source: null, passage: '', note: '', created_at: now, updated_at: now,
      ...annotation, id: newId(),
    };
    return this.#annotation(
      (list) => {
        if (!list.some((a) => a.id === draft.id)) list.push({ ...draft });
      },
      () => api.post<{ annotation: Annotation }>('/api/annotations', { ...annotation, id: draft.id }),
      ({ annotation: saved }) => {
        const list = this.state?.annotations;
        const index = list?.findIndex((a) => a.id === saved.id) ?? -1;
        if (index >= 0) list![index] = saved;
        else list?.push(saved);
      },
    );
  }

  /** Changes a note's text and, when `images` is given, its images. */
  editNote(id: string, note: string, images?: string[]) {
    const text = note.trim();
    return this.#annotation(
      (list) => {
        const item = list.find((a) => a.id === id);
        if (!item) return;
        item.note = text;
        if (images) item.images = images.length ? images : undefined;
      },
      () => api.put(`/api/annotations/${encodeURIComponent(id)}`, images ? { note, images } : { note }),
    );
  }

  removeAnnotation(id: string) {
    return this.#annotation(
      (list) => drop(list, id),
      () => api.delete(`/api/annotations/${encodeURIComponent(id)}`),
    );
  }

  /** Preferences the teacher suggested in these turns' memory notes, whose entries are named `<turn id>:<index>`. */
  suggestedBy(turnIds: string[]) {
    return (this.state?.memory ?? []).filter((e) => e.status === 'suggested' && turnIds.includes(e.id.slice(0, e.id.lastIndexOf(':'))));
  }

  /** An entry the learner writes down themselves; a preference is saved confirmed. */
  addMemory(kind: MemoryEntry['kind'], text: string, conceptId?: string | null) {
    return this.act(() => api.post('/api/memory', { kind, text, ...(conceptId ? { concept_id: conceptId } : {}) }));
  }

  editMemory(id: string, text: string) {
    return this.act(() => api.put(`/api/memory/${encodeURIComponent(id)}`, { text }));
  }

  confirmMemory(id: string) {
    return this.act(() => api.post(`/api/memory/${encodeURIComponent(id)}/confirm`));
  }

  /** Deleting is final, and dismissing a suggested preference is a delete: the same evidence does not bring it back. */
  removeMemory(id: string) {
    return this.act(() => api.delete(`/api/memory/${encodeURIComponent(id)}`));
  }

  toggleBookmark(conceptId: string, source?: AnnotationSource | null) {
    const existing = this.bookmark(conceptId, source);
    if (existing) return this.removeAnnotation(existing.id);
    return this.annotate({ kind: 'bookmark', concept_id: conceptId, ...(source ? { source } : {}) });
  }

  showAnnotation(id: string) {
    this.focusAnnotation = id;
    this.openPanel('notes');
  }

  /** Brings an annotation's lesson passage or source back into view. */
  async goTo(annotation: Annotation) {
    if (annotation.source) {
      void this.openSource({ ...annotation.source });
      return;
    }
    const turn = this.turn(annotation.turn_id);
    if (turn?.channel === 'sidequestion') {
      const question = this.state?.questions.find(
        (q) => q.turn_id === turn.id || q.supplement_turn_id === turn.id || q.replies?.some((r) => r.turn_id === turn.id),
      );
      if (question) {
        this.focusThread = question.id;
        this.openPanel('questions');
      }
      return;
    }
    const chapter = this.ownerChapter(annotation);
    if (chapter) this.viewChapter(chapter);
    else this.view(annotation.concept_id);
    if (annotation.task_id) {
      await tick();
      requestAnimationFrame(() => {
        const exercise = document.getElementById(`exercise-${annotation.task_id}`);
        if (!exercise) return;
        // The passage may be in the question or the teacher's feedback; land on it, else on the exercise.
        const range = annotation.passage
          ? [...exercise.querySelectorAll<HTMLElement>('[data-exercise]')].map((block) => occurrences(block, annotation.passage)[annotation.occurrence ?? 0]).find(Boolean)
          : undefined;
        if (range) scrollStage(Math.max(0, stageOffset(range.getBoundingClientRect().top) - stageHeight() / 3));
        else exercise.scrollIntoView({ block: 'center', behavior: 'instant' });
      });
      return;
    }
    if (annotation.turn_id) await this.#scrollToLesson(annotation.turn_id, annotation.passage, { occurrence: annotation.occurrence ?? 0 });
  }

  /** A section's own exercises, oldest first, each variant right after the exercise it was written like; chapter quiz
   * questions anchored to the section are listed on the chapter page. */
  tasks(conceptId: string | null): Task[] {
    const own = (this.state?.practice.tasks ?? []).filter((t) => t.concept_id === conceptId && !t.chapter_id).sort((a, b) => (a.created_at ?? 0) - (b.created_at ?? 0));
    const ids = new Set(own.map((t) => t.id));
    const ordered: Task[] = [];
    const place = (task: Task) => {
      ordered.push(task);
      own.filter((t) => t.variant_of === task.id).forEach(place);
    };
    own.filter((t) => !t.variant_of || !ids.has(t.variant_of)).forEach(place);
    return ordered;
  }

  /** The chapter's quiz questions, oldest quiz first. */
  quizTasks(chapterId: string | null | undefined): Task[] {
    return (this.state?.practice.tasks ?? []).filter((t) => !!chapterId && t.chapter_id === chapterId).sort((a, b) => (a.created_at ?? 0) - (b.created_at ?? 0));
  }

  openPanel(tab: PanelTab) {
    this.panelTab = tab;
    this.panelOpen = true;
  }

  /** Sets the panel width; a width the learner chose is kept for later visits unless `save` defers that. */
  resizePanel(width: number, chosen = true, save = chosen) {
    this.panelWidth = Math.round(Math.min(Math.max(width, 320), window.innerWidth * 0.62));
    if (!chosen) return;
    this.#widthChosen = true;
    if (save) this.savePanelWidth();
  }

  /** The route shows as its folded capsule; on a phone it is a drawer instead. */
  get folded() {
    return !this.phone && (this.stageNarrow || this.routeFolded);
  }

  /** Fold or unfold the route; only possible when the stage has room for it unfolded. */
  toggleRoute() {
    if (this.stageNarrow || this.phone) return;
    this.routeFolded = !this.routeFolded;
    try {
      localStorage.setItem('route-folded', this.routeFolded ? 'yes' : '');
    } catch {
      // The choice still applies for this visit.
    }
  }

  savePanelWidth() {
    try {

      localStorage.setItem('panel-width', String(this.panelWidth));
    } catch {
      // The width still applies for this visit.
    }
  }

  /** Source revisions never change, so each location is fetched once. */
  sourceView(ref: Ref): Promise<SourceView> {
    const key = `${ref.source_id}/${ref.revision}/${ref.unit_id}`;
    let view = this.#sources.get(key);
    if (!view) {
      view = api.get<SourceView>(`/api/sources/${ref.source_id}/${ref.revision}/${encodeURIComponent(ref.unit_id)}`);
      view.catch(() => this.#sources.delete(key));
      this.#sources.set(key, view);
    }
    return view;
  }

  async openSource(ref: Ref) {
    const request = ++this.#sourceRequest;
    this.openPanel('source');
    this.sourceList = false;
    this.sourceLoading = true;
    try {
      const view = await this.sourceView(ref);
      if (request !== this.#sourceRequest) return;
      this.source = view;
      // A page of a PDF needs room; widen once unless the learner has chosen a width.
      if (view.pdf_url && !this.#widthChosen) this.resizePanel(Math.max(this.panelWidth, window.innerWidth * 0.42), false);
    } catch (e) {
      if (request !== this.#sourceRequest) return;
      this.source = null;
      this.error = (e as Error).message;
    } finally {
      if (request === this.#sourceRequest) this.sourceLoading = false;
    }
  }

  viewChapter(chapterId: string) {
    this.viewingChapter = chapterId;
    this.reviewOpen = false;
    this.routeOpen = false;
    this.#chapterToggles = { at: null, open: {} };
    scrollStage(0);
  }

  /** Moving the position lands on the new section, unless the learner has gone elsewhere while it was being made. */
  async #move(action: () => Promise<unknown>) {
    const before = [this.viewing, this.viewingChapter, this.reviewOpen];
    if (await this.act(action)) {
      const after = [this.viewing, this.viewingChapter, this.reviewOpen];
      if (after.some((value, i) => value !== before[i])) return;
      this.viewing = this.viewingChapter = null;
      this.reviewOpen = false;
      scrollStage(0);
    }
  }

  showReview() {
    this.reviewOpen = true;
    this.libraryOpen = false;
    this.routeOpen = false;
    scrollStage(0);
  }

  /** Ask for a review set (ADR 0014): nothing for Review for me, or a request and scope, or the section a warm-up comes before. */
  askReview(body: { request?: string; scope?: { chapter_ids?: string[]; concept_ids?: string[] }; warm_up_for?: string } = {}) {
    return this.act(() => api.post('/api/review/sets', body));
  }

  closeReviewSet(setId: string) {
    return this.act(() => api.post(`/api/review/sets/${encodeURIComponent(setId)}/close`, {}));
  }

  /** A recall question's choice; its feedback was written with it, so nothing waits for the teacher. */
  answerRecall(taskId: string, choice: CheckChoice) {
    return this.act(() => api.post(`/api/review/tasks/${encodeURIComponent(taskId)}/answer`, { choice }));
  }

  dismissWarmUp(conceptId: string) {
    return this.act(() => api.post(`/api/review/warm-ups/${encodeURIComponent(conceptId)}/dismiss`, {}));
  }

  /** Revisit a missed review question: a new side question quoting it, ready to send (ADR 0014). */
  revisit(question: string) {
    this.quote = { text: question, turnId: null, scrollY: stageScroll() };
    if (!this.drafts.get('question').trim()) this.drafts.set('question', t("I missed this in review. Can you go over the idea again?"));
    this.openPanel('questions');
    requestAnimationFrame(() => document.getElementById('question-input')?.focus());
  }

  /** A recap and the chapter quiz stay on the chapter page and never move the learner's position. */
  recapChapter(chapterId: string) {
    return this.act(() => api.post(`/api/chapters/${encodeURIComponent(chapterId)}/recap`, { id: `recap:${newId()}` }));
  }

  takeQuiz(chapterId: string) {
    return this.act(() => api.post(`/api/chapters/${encodeURIComponent(chapterId)}/quiz`));
  }

  buildChapter(chapterId: string) {
    return this.act(() => api.post(`/api/chapters/${encodeURIComponent(chapterId)}/build`));
  }

  skipChapter(chapterId: string) {
    return this.#move(() => api.post(`/api/chapters/${encodeURIComponent(chapterId)}/skip`, { request_id: newId() }));
  }

  /** Study a later section now; the unstudied sections passed over stay on the route as skipped (ADR 0006). */
  jumpTo(conceptId: string) {
    return this.#move(() => api.post('/api/sections/jump', { concept_id: conceptId, request_id: newId() }));
  }

  studySkipped(conceptId: string) {
    return this.#move(() => api.post('/api/sections/enter', { concept_id: conceptId, request_id: newId() }));
  }

  startLesson(prompt: string) {
    return this.act(() => api.post('/api/lessons', { id: newId(), prompt }));
  }

  /** Continue: teach the next planned step of a stepped lesson. */
  continueLesson(lessonId: string) {
    return this.act(() => api.post(`/api/lessons/${encodeURIComponent(lessonId)}/steps`, { id: newId() }));
  }

  /** Answers a step's check question; its explanation is already in the lesson, so no model turn follows. */
  answerCheck(lessonId: string, turnId: string, choice: CheckChoice) {
    return this.act(() =>
      api.post(`/api/lessons/${encodeURIComponent(lessonId)}/steps/${encodeURIComponent(turnId)}/check`, { choice }),
    );
  }

  async setLanguage(language: Language) {
    if (!this.state) {
      locale.language = rememberLanguage(language) ?? language;
      return;
    }
    const result = await this.savePreferences({ language });
    if (result) {
      locale.language = result.language;
      rememberLanguage(locale.language);
    }
  }

  /** Saves the learner's teacher settings; counted, so a state load that started earlier cannot put older ones back. */
  async saveSettings(changes: Omit<Settings, 'overridden' | 'path'>) {
    const result = await this.act(() => api.put<Settings>('/api/settings', changes));
    if (result) {
      this.#settingsWrites++;
      this.settings = result;
    }
    return result;
  }

  /** Saves some of the course's preferences; the others keep their value. */
  async savePreferences(changes: Partial<Preferences>) {
    const result = await this.act(() => api.put<{ preferences: Preferences }>('/api/preferences', changes));
    if (result && this.state) this.state.preferences = result.preferences;
    return result?.preferences ?? null;
  }

  pause(turnId: string) {
    return this.act(() => api.post(`/api/turns/${encodeURIComponent(turnId)}/pause`));
  }

  regenerate(turnId: string) {
    return this.act(() => api.post(`/api/turns/${encodeURIComponent(turnId)}/resume`, { request_id: newId() }));
  }
}

export const app = new AppStore();
