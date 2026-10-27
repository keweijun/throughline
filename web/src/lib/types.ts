export type Ref = { source_id: string; revision: string; unit_id: string; detail?: string };

export type Concept = {
  id: string;
  title: string;
  prerequisites?: string[];
  links?: Ref[];
  exercises?: Ref[];
  objective?: string;
  goal?: string;
};

export type Coverage = Ref & {
  concept_ids?: string[];
  disposition: 'mapped' | 'deferred' | 'needs_review';
  reason?: string;
  verification?: 'pending' | 'verified';
};

/** A table-of-contents grouping of route sections; a chapter with no sections is not built yet. */
export type Chapter = { id: string; title: string; summary?: string; concept_ids: string[] };

/** A section deferred when the learner skipped its chapter, until a lesson there is studied. */
export type Skipped = { id: string; concept_id: string; section_id: string; target_concept_id?: string };

export type Position = {
  concept_id?: string;
  goal?: string;
  next_step?: string;
  progress?: string;
};

export type TurnStatus = 'running' | 'completed' | 'paused' | 'interrupted' | 'failed';

export type Turn = {
  id: string;
  concept_id: string;
  /**
   * Set on a chapter recap: it belongs to the chapter page, and `concept_id` (the chapter's last section) is only the
   * anchor for section-scoped records.
   */
  chapter_id?: string;
  channel: 'mainline' | 'sidequestion' | 'practice' | 'preparation' | 'build';
  prompt: string;
  status: TurnStatus;
  attempt: number;
  /** The last stream event applied to `text`; streamed deltas carry the next one. */
  sequence: number;
  text: string;
  final_text?: string | null;
  error?: string;
  started_at: number;
  source_refs?: Ref[];
  attempts: { attempt: number; text: string; status: TurnStatus }[];
  metrics: Record<string, number>;
  title?: string | null;
};

/** One step of a stepped lesson (ADR 0009); `turn_id` is set once the step is taught, `replied` once its plan block is read. */
export type LessonStep = { title: string; added: boolean; turn_id?: string; replied?: boolean };

/** A section's lesson taught in steps, one mainline turn each. Lessons saved before steps have no record. */
export type SteppedLesson = { id: string; concept_id: string; request: string; created_at: number; steps: LessonStep[] };

export type Decision = {
  depth: 'short' | 'long';
  category: string;
  rationale: string;
  suggest_supplement: boolean;
  supplement_goal?: string;
  target_concept_id?: string;
};

export type QuestionReply = { id: string; question: string; selection: string; turn_id: string; created_at: number };

export type Question = {
  created_at?: number;
  replies?: QuestionReply[];
  id: string;
  question: string;
  selection: string;
  anchor: { scroll_y?: number; concept_id?: string | null };
  restore_point: Position;
  main_turn_id: string | null;
  selected_turn_id: string | null;
  turn_id: string;
  status: 'unanswered' | 'answered' | 'suggested' | 'supplement';
  decision: Decision | null;
  choice: 'accept' | 'decline' | null;
  supplement_turn_id?: string;
  returned?: boolean;
};

export type EvidenceKind = 'independent' | 'retest_passed' | 'hinted' | 'needs_work';

export type PracticeHistory = {
  action: PracticeAction;
  feedback: string;
  outcome?: 'passed' | 'needs_work';
  kind?: EvidenceKind;
  answer?: string;
  /** An ask: the learner's question, answered and never assessed (ADR 0011). */
  question?: string;
};

export type Task = {
  id: string;
  concept_id: string;
  question: string;
  /**
   * `review` and `chapter_quiz` are retrieval questions (ADR 0008). A chapter quiz question belongs to its chapter
   * (`chapter_id`, anchored to the last section), names the sections it tests and, when it asks an earlier exercise
   * again, the exercise it came from.
   */
  origin: 'source' | 'self_created' | 'review' | 'chapter_quiz';
  tests_concept_ids?: string[];
  chapter_id?: string;
  quiz_id?: string;
  from_task_id?: string;
  created_at?: number;
  source_refs: Ref[];
  status: 'pending' | 'attempted' | 'deferred' | 'skipped';
  skip_reason?: 'too_easy' | 'too_tedious' | 'not_relevant';
  history: PracticeHistory[];
};

export type PracticeAction = 'hint' | 'steps' | 'solution' | 'assess' | 'ask';

export type PracticeJob = {
  answer?: string;
  question?: string;
  id: string;
  concept_id: string;
  action: 'generate' | PracticeAction;
  task_id?: string;
  purpose?: 'review' | 'chapter_quiz';
  chapter_id?: string;
  processed?: boolean;
  error?: string;
};

export type PreparationJob = {
  id: string;
  concept_id: string;
  status: 'running' | 'ready' | 'deferred' | 'failed' | 'stale';
  reason?: string;
};

/** The app building an outlined chapter in the background; `interrupted` means the host stopped mid-build. */
export type ChapterBuild = {
  chapter_id: string;
  status: 'queued' | 'building' | 'failed' | 'interrupted' | 'done';
  trigger: 'learner' | 'auto';
  attempt: number;
  error?: string;
  discarded?: boolean;
};

export type Settings = {
  model: string;
  small_model: string;
  effort: 'minimal' | 'low' | 'medium' | 'high';
  small_effort: '' | 'minimal' | 'low' | 'medium' | 'high';
  service_tier: string;
  overridden: boolean;
  path: string;
};

export type ServiceTier = { id: string; name: string; description: string };

export type CodexModel = {
  id: string;
  name: string;
  description: string;
  default: boolean;
  efforts: string[];
  tiers: ServiceTier[];
};

export type DeferredExplanation = {
  id: string;
  target_concept_id: string;
  status: 'pending' | 'resolved';
  question: string;
  provisional_answer: string;
  answer_interaction_id?: string;
};

export type Interaction = { id: string; role: 'user' | 'assistant'; text: string; concept_id?: string };

export type State = {
  preferences: { language: 'en' | 'zh-CN' };
  course: { id: string; title: string };
  position: Position | null;
  sources: { id: string; path: string; revision: string; status: string }[];
  curriculum: { concepts: Concept[]; route: string[]; coverage?: Coverage[]; chapters?: Chapter[] };
  session: {
    position?: Position | null;
    recent_interactions: Interaction[];
    unanswered_questions: { id: string; question?: string; concept_id?: string }[];
    due_explanations: DeferredExplanation[];
  };
  deferred_explanations: DeferredExplanation[];
  turns: Turn[];
  lessons: SteppedLesson[];
  questions: Question[];
  practice: { tasks: Task[]; jobs: PracticeJob[] };
  preparation: { jobs: PreparationJob[]; next_concept_id: string | null };
  settings: Settings;
  annotations: Annotation[];
  skipped: Skipped[];
  builds: ChapterBuild[];
  review: ReviewState;
};

/** A section's place in the spaced review schedule; `task_id` is its review question once started. */
export type ReviewSection = {
  concept_id: string;
  step: number;
  interval_days: number;
  due_at: number;
  last_review_at: number | null;
  task_id: string | null;
};

/** Due sections (oldest first, at most `cap` a day counting `done_today`), with the review questions and their requests. */
export type ReviewState = {
  due: ReviewSection[];
  waiting: number;
  upcoming: number;
  next_due_at: number | null;
  reviewable: number;
  done_today: number;
  cap: number;
  now: number;
  sections: ReviewSection[];
  tasks: Task[];
  jobs: PracticeJob[];
};

export type AnnotationSource = Ref & { label?: string; page?: number };

/** The learner's own highlight, note or bookmark. Never sent to the teacher. */
export type Annotation = {
  id: string;
  kind: 'highlight' | 'note' | 'bookmark';
  concept_id: string;
  turn_id: string | null;
  task_id?: string | null;
  source: AnnotationSource | null;
  passage: string;
  note: string;
  created_at: number;
  updated_at: number;
};

export type Overview = {
  core_problem: string;
  steps: string[];
  prior: string;
  next: string;
  target_ability: string;
  origin: 'teacher' | 'route_summary';
};

export type Preview = {
  concept: Concept;
  prerequisites: Concept[];
  next_concept_id: string | null;
  overview: Overview;
  sources: (Ref & { verification: string; stale?: boolean; locator?: { page?: number; line?: number } })[];
  set_aside: (Ref & { disposition: 'deferred' | 'needs_review'; reason: string })[];
};

export type SourceView = Ref & {
  title: string;
  kind: string;
  text?: string;
  locator?: { page?: number; line?: number };
  verification: string;
  stale: boolean;
  image_url: string | null;
  pdf_url: string | null;
  render_message: string | null;
  document: { id: string; text: string }[] | null;
};

/** Streamed text for a running turn; `sequence` is the turn's stream event it came from. */
export type DeltaEvent = { type: 'delta'; id: string; attempt: number; sequence: number; text: string };

export type ChangeScope = 'state' | 'course' | 'library' | 'settings' | 'preferences' | 'preparation';

export type HostEvent = DeltaEvent | { type: 'turn'; turn: Turn } | { type: 'changed'; scope: ChangeScope };


export type LibraryCourse = {
  name: string;
  path: string;
  title?: string;
  sources?: number;
  concepts?: number;
  needs_review?: number;
  current?: string | null;
  goal?: string | null;
  updated?: number;
  error?: string;
};

export type Library = { root: string | null; active: string | null; courses: LibraryCourse[] };
