import { tick } from 'svelte';
import { locale, type Language } from './i18n.svelte';
import { api, ApiError, newId } from './api';
import { locate } from './highlight';
import { scrollStage, stageHeight, stageOffset } from './stage';
import type { Annotation, AnnotationSource, Chapter, ChapterBuild, DeltaEvent, HostEvent, Library, Question, Ref, Settings, SourceView, State, Task, Turn } from './types';

export type PanelTab = 'questions' | 'source' | 'notes' | 'memory';
export type Connection = 'connecting' | 'live' | 'reconnecting';
export type Quote = { text: string; turnId: string | null; scrollY: number; source?: string; questionId?: string };

const DEFAULT_PANEL = 400;

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
  notice = $state<string | null>(null);
  library = $state<Library | null>(null);
  libraryOpen = $state(false);
  /** Teacher settings belong to the learner, so they are available before a course is open. */
  settings = $state<Settings | null>(null);

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
  routeOpen = $state(false);
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
  #noticeTimer: ReturnType<typeof setTimeout> | null = null;
  #refreshing: Promise<void> | null = null;
  #again = false;
  /** Deltas that arrive while a state snapshot is in flight; replayed onto the snapshot so no text is lost. */
  #inflight: DeltaEvent[] | null = null;

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

  hasLesson(conceptId: string | null) {
    return this.lessons(conceptId).some((t) => t.status === 'completed' || t.status === 'running');
  }

  get runningLesson() {
    return this.state?.turns.find((t) => t.channel === 'mainline' && t.status === 'running') ?? null;
  }

  isRunning(turnId: string | null | undefined) {
    return this.turn(turnId)?.status === 'running';
  }

  /** Loads the course state; sync() is the entry point, so two loads never race. */
  async #load() {
    this.#inflight = [];
    try {
      const state = await api.get<State>('/api/state');
      const missed = this.#inflight;
      this.state = state;
      for (const delta of missed) this.#delta(delta);
      this.settings = this.state.settings;
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
          [this.settings] = await Promise.all([api.get<Settings>('/api/settings'), this.loadLibrary()]);
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

  refresh() {
    if (this.#refreshTimer) return;
    this.#refreshTimer = setTimeout(() => {
      this.#refreshTimer = null;
      void this.sync();
    }, 120);
  }

  /**
   * Reloads the state, one load at a time. A request made while a load runs queues one more load, and the returned
   * promise settles once the state reflects everything requested so far.
   */
  sync(): Promise<void> {
    if (this.#refreshing) {
      this.#again = true;
      return this.#refreshing;
    }
    this.#refreshing = (async () => {
      try {
        do {
          this.#again = false;
          await this.#load();
        } while (this.#again);
      } catch (e) {
        this.error = (e as Error).message;
      } finally {
        this.#refreshing = null;
      }
    })();
    return this.#refreshing;
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
      if (event.turn.status !== 'running') this.refresh();
    } else {
      this.refresh();
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

  /** A short confirmation that clears itself. */
  notify(text: string) {
    this.notice = text;
    if (this.#noticeTimer) clearTimeout(this.#noticeTimer);
    this.#noticeTimer = setTimeout(() => (this.notice = null), 8000);
  }

  view(conceptId: string) {
    this.viewingChapter = null;
    this.reviewOpen = false;
    this.viewing = conceptId === this.currentId ? null : conceptId;
    this.routeOpen = false;
    scrollStage(0);
  }

  /**
   * Once the reading column has re-rendered, scrolls to a passage in a lesson, else to `fallback` (a page offset),
   * else to the lesson itself. `near` picks between repeated occurrences of the passage.
   */
  async #scrollToLesson(turnId: string | null | undefined, passage: string | null | undefined, options: { near?: number; fallback?: number } = {}) {
    await tick();
    requestAnimationFrame(() => {
      const lesson = turnId ? document.getElementById(`turn-${turnId}`) : null;
      const body = lesson?.querySelector<HTMLElement>('.lesson-body');
      const range = body && passage ? locate(body, passage, options.near) : null;
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

  annotate(annotation: Pick<Annotation, 'kind' | 'concept_id'> & Partial<Pick<Annotation, 'passage' | 'note' | 'turn_id' | 'task_id' | 'source'>>) {
    return this.act(() => api.post<{ annotation: Annotation }>('/api/annotations', annotation));
  }

  editNote(id: string, note: string) {
    return this.act(() => api.put(`/api/annotations/${encodeURIComponent(id)}`, { note }));
  }

  removeAnnotation(id: string) {
    return this.act(() => api.delete(`/api/annotations/${encodeURIComponent(id)}`));
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
      requestAnimationFrame(() => document.getElementById(`exercise-${annotation.task_id}`)?.scrollIntoView({ block: 'center', behavior: 'instant' }));
      return;
    }
    if (annotation.turn_id) await this.#scrollToLesson(annotation.turn_id, annotation.passage);
  }

  /** A section's own exercises; chapter quiz questions anchored to it are listed on the chapter page. */
  tasks(conceptId: string | null): Task[] {
    return (this.state?.practice.tasks ?? []).filter((t) => t.concept_id === conceptId && !t.chapter_id);
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
    scrollStage(0);
  }

  /** Moving the position always lands on the new section. */
  async #move(action: () => Promise<unknown>) {
    if (await this.act(action)) {
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

  startReview(conceptId: string) {
    return this.act(() => api.post('/api/review/start', { concept_id: conceptId }));
  }

  postponeReview(conceptId: string) {
    return this.act(() => api.post('/api/review/postpone', { concept_id: conceptId }));
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

  studySkipped(conceptId: string) {
    return this.#move(() => api.post('/api/sections/enter', { concept_id: conceptId, request_id: newId() }));
  }

  startLesson(prompt: string) {
    return this.act(() => api.post('/api/lessons', { id: newId(), prompt }));
  }

  async setLanguage(language: Language) {
    if (!this.state) {
      locale.language = rememberLanguage(language) ?? language;
      return;
    }
    const result = await this.act(() => api.put<{ preferences: { language: Language } }>('/api/preferences', { language }));
    if (result) {
      locale.language = result.preferences.language;
      rememberLanguage(locale.language);
      if (this.state) this.state.preferences = result.preferences;
    }
  }

  pause(turnId: string) {
    return this.act(() => api.post(`/api/turns/${encodeURIComponent(turnId)}/pause`));
  }

  regenerate(turnId: string) {
    return this.act(() => api.post(`/api/turns/${encodeURIComponent(turnId)}/resume`, { request_id: newId() }));
  }
}

export const app = new AppStore();
