import { tick } from 'svelte';
import { locale, type Language } from './i18n.svelte';
import { api, ApiError, newId } from './api';
import { locate } from './highlight';
import type { HostEvent, Library, Question, Ref, Settings, SourceView, State, Task, Turn } from './types';

export type PanelTab = 'questions' | 'source';
export type Connection = 'connecting' | 'live' | 'reconnecting';
export type Quote = { text: string; turnId: string | null; scrollY: number; source?: string };

const DEFAULT_PANEL = 400;

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

  panelOpen = $state(false);
  panelTab = $state<PanelTab>('questions');
  source = $state<SourceView | null>(null);
  sourceLoading = $state(false);
  quote = $state<Quote | null>(null);
  settingsOpen = $state(false);
  routeOpen = $state(false);
  shortcutsOpen = $state(false);
  /** Question thread to scroll to and flash in the side panel. */
  focusThread = $state<string | null>(null);
  panelWidth = $state(storedWidth());
  #widthChosen = storedWidth() !== DEFAULT_PANEL;
  #sources = new Map<string, Promise<SourceView>>();

  #refreshTimer: ReturnType<typeof setTimeout> | null = null;
  #refreshing: Promise<void> | null = null;
  #again = false;

  get currentId(): string | null {
    const s = this.state;
    return s?.position?.concept_id ?? s?.curriculum.route[0] ?? null;
  }

  get viewingId(): string | null {
    return this.viewing ?? this.currentId;
  }

  concept(id: string | null | undefined) {
    return this.state?.curriculum.concepts.find((c) => c.id === id);
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
      this.error = null;
    } catch (e) {
      if (e instanceof ApiError && e.code === 'no_course') {
        this.state = null;
        this.libraryOpen = true;
        [this.settings] = await Promise.all([api.get<Settings>('/api/settings'), this.loadLibrary()]);
      } else this.error = (e as Error).message;
    }
  }

  async loadLibrary() {
    try {
      this.library = await api.get<Library>('/api/library');
    } catch (e) {
      this.error = (e as Error).message;
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

  view(conceptId: string) {
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

  startLesson(prompt: string) {
    return this.act(() => api.post('/api/lessons', { id: newId(), prompt }));
  }

  async setLanguage(language: Language) {
    const result = await this.act(() => api.put<{ preferences: { language: Language } }>('/api/preferences', { language }));
    if (result) {
      locale.language = result.preferences.language;
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
