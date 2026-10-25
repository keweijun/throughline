import { tick } from 'svelte';
import { locale, type Language } from './i18n.svelte';
import { api, ApiError, newId } from './api';
import { locate } from './highlight';
import type { Annotation, AnnotationSource, Chapter, HostEvent, Library, Question, Ref, Settings, SourceView, State, Task, Turn } from './types';

export type PanelTab = 'questions' | 'source' | 'notes';
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

  #refreshTimer: ReturnType<typeof setTimeout> | null = null;
  #noticeTimer: ReturnType<typeof setTimeout> | null = null;
  #refreshing: Promise<void> | null = null;
  #again = false;

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

  isSkipped(conceptId: string | null | undefined) {
    return (this.state?.skipped ?? []).some((s) => s.concept_id === conceptId);
  }

  routeIndex(id: string | null | undefined) {
    return id ? (this.state?.curriculum.route.indexOf(id) ?? -1) : -1;
  }

  lessons(conceptId: string | null): Turn[] {
    return (this.state?.turns ?? []).filter((t) => t.channel === 'mainline' && t.concept_id === conceptId);
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

  async load() {
    try {
      this.state = await api.get<State>('/api/state');
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
        [this.settings] = await Promise.all([api.get<Settings>('/api/settings'), this.loadLibrary()]);
      } else this.error = (e as Error).message;
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
      void this.#runRefresh();
    }, 120);
  }

  async #runRefresh() {
    if (this.#refreshing) {
      this.#again = true;
      return;
    }
    this.#refreshing = this.load();
    await this.#refreshing;
    this.#refreshing = null;
    if (this.#again) {
      this.#again = false;
      await this.#runRefresh();
    }
  }

  connect() {
    const events = new EventSource('/api/events');
    events.onopen = () => {
      // Anything may have changed while disconnected.
      if (this.connection !== 'connecting') void this.load();
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
    const turns = this.state?.turns;
    if (!turns) {
      if (event.type === 'changed') this.refresh();
      return;
    }
    if (event.type === 'delta') {
      const turn = turns.find((t) => t.id === event.id);
      if (turn && turn.attempt === event.attempt && turn.status === 'running') turn.text += event.text;
      else this.refresh();
    } else if (event.type === 'turn') {
      const index = turns.findIndex((t) => t.id === event.turn.id);
      if (index >= 0) turns[index] = event.turn;
      else turns.push(event.turn);
      if (event.turn.status !== 'running') this.refresh();
    } else {
      this.refresh();
    }
  }

  /** Runs an action, reporting failures in the shared error banner. Returns undefined on failure. */
  async act<T>(action: () => Promise<T>): Promise<T | undefined> {
    this.error = null;
    try {
      const result = await action();
      this.refresh();
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
    this.viewing = conceptId === this.currentId ? null : conceptId;
    this.routeOpen = false;
    window.scrollTo({ top: 0 });
  }

  /** Brings the reading column back to the passage a question was about, falling back to where the learner was reading. */
  async returnTo(question: Question) {
    if (this.currentId) this.view(this.currentId);
    await tick();
    requestAnimationFrame(() => {
      const lesson = document.getElementById(`turn-${question.selected_turn_id ?? question.main_turn_id}`);
      const body = lesson?.querySelector<HTMLElement>('.lesson-body');
      const sameSection = question.anchor?.concept_id === this.currentId && question.anchor.scroll_y != null;
      const near = sameSection ? question.anchor.scroll_y! + window.innerHeight / 2 : undefined;
      const range = body && question.selection ? locate(body, question.selection, near) : null;
      let top: number | null = null;
      if (range) top = range.getBoundingClientRect().top + window.scrollY - window.innerHeight / 3;
      else if (sameSection) top = question.anchor.scroll_y!;
      else if (lesson) top = lesson.getBoundingClientRect().top + window.scrollY - 80;
      window.scrollTo({ top: Math.max(0, top ?? 0), behavior: 'instant' });
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
    this.view(annotation.concept_id);
    if (annotation.task_id) {
      await tick();
      requestAnimationFrame(() => document.getElementById(`exercise-${annotation.task_id}`)?.scrollIntoView({ block: 'center', behavior: 'instant' }));
      return;
    }
    if (!annotation.turn_id) return;
    await tick();
    requestAnimationFrame(() => {
      const lesson = document.getElementById(`turn-${annotation.turn_id}`);
      const body = lesson?.querySelector<HTMLElement>('.lesson-body');
      const range = body && annotation.passage ? locate(body, annotation.passage) : null;
      const box = range?.getBoundingClientRect() ?? lesson?.getBoundingClientRect();
      if (box) window.scrollTo({ top: Math.max(0, box.top + window.scrollY - window.innerHeight / 3), behavior: 'instant' });
    });
  }

  tasks(conceptId: string | null): Task[] {
    return (this.state?.practice.tasks ?? []).filter((t) => t.concept_id === conceptId);
  }

  openPanel(tab: PanelTab) {
    this.panelTab = tab;
    this.panelOpen = true;
  }

  resizePanel(width: number, chosen = true) {
    this.panelWidth = Math.round(Math.min(Math.max(width, 320), window.innerWidth * 0.62));
    if (!chosen) return;
    this.#widthChosen = true;
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
    this.openPanel('source');
    this.sourceList = false;
    this.sourceLoading = true;
    try {
      this.source = await this.sourceView(ref);
      // A page of a PDF needs room; widen once unless the learner has chosen a width.
      if (this.source.pdf_url && !this.#widthChosen) this.resizePanel(Math.max(this.panelWidth, window.innerWidth * 0.42), false);
    } catch (e) {
      this.source = null;
      this.error = (e as Error).message;
    } finally {
      this.sourceLoading = false;
    }
  }

  viewChapter(chapterId: string) {
    this.viewingChapter = chapterId;
    this.routeOpen = false;
    window.scrollTo({ top: 0 });
  }

  /** Moving the position always lands on the new section. */
  async #move(action: () => Promise<unknown>) {
    if (await this.act(action)) {
      this.viewing = this.viewingChapter = null;
      window.scrollTo({ top: 0 });
    }
  }

  recapChapter(chapterId: string) {
    return this.#move(() => api.post(`/api/chapters/${encodeURIComponent(chapterId)}/recap`, { id: `recap:${newId()}` }));
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
