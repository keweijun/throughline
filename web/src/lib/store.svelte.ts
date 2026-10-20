import { locale, type Language } from './i18n.svelte';
import { api, ApiError, newId } from './api';
import type { HostEvent, Preview, Ref, SourceView, State, Turn } from './types';

export type PanelTab = 'questions' | 'source';
export type Connection = 'connecting' | 'live' | 'reconnecting';
export type Quote = { text: string; turnId: string; scrollY: number };

class AppStore {
  state = $state<State | null>(null);
  connection = $state<Connection>('connecting');
  error = $state<string | null>(null);
  notice = $state<string | null>(null);

  /** Concept shown in the reading column; null follows the formal position. */
  viewing = $state<string | null>(null);
  preview = $state<Preview | null>(null);

  panelOpen = $state(false);
  panelTab = $state<PanelTab>('questions');
  source = $state<SourceView | null>(null);
  sourceLoading = $state(false);
  quote = $state<Quote | null>(null);
  settingsOpen = $state(false);
  routeOpen = $state(false);

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
      locale.language = this.state.preferences.language;
      this.error = null;
    } catch (e) {
      this.error = (e as Error).message;
    }
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
    const turns = this.state?.turns;
    if (!turns) return;
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

  async loadPreview(conceptId: string) {
    this.preview = null;
    try {
      this.preview = await api.get<Preview>(`/api/concepts/${encodeURIComponent(conceptId)}/preview`);
    } catch (e) {
      this.error = (e as Error).message;
    }
  }

  openPanel(tab: PanelTab) {
    this.panelTab = tab;
    this.panelOpen = true;
  }

  async openSource(ref: Ref) {
    this.openPanel('source');
    this.sourceLoading = true;
    try {
      this.source = await api.get<SourceView>(`/api/sources/${ref.source_id}/${ref.revision}/${encodeURIComponent(ref.unit_id)}`);
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
