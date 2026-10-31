export type Ref = { source_id: string; revision: string; unit_id: string; detail?: string };

export type Concept = {
  id: string;
  title: string;
  prerequisites?: string[];
  links?: Ref[];
  exercises?: CourseExercise[];
  objective?: string;
  goal?: string;
};

/**
 * An original exercise mapped to a section. A part split from a homework question names the question (`part_of`) and
 * its other parts, with the section teaching each; a part without `concept_id` waits for a chapter not built yet (ADR 0012).
 */
export type CourseExercise = Ref & { question?: string; part_of?: string; other_parts?: { question: string; concept_id?: string }[] };

export type Coverage = Ref & {
  concept_ids?: string[];
  disposition: 'mapped' | 'deferred' | 'needs_review';
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

/** A turn's channel, as `CHANNELS` in guided_learning/streaming.py: the learner's own requests, then background work. */
export type Channel = 'mainline' | 'sidequestion' | 'practice' | 'prepared_step' | 'preparation' | 'build' | 'consolidation';

/** Why an exercise was skipped, as practice.SKIP_REASONS (ADR 0011). */
export type SkipReason = 'too_easy' | 'too_tedious' | 'not_relevant';

export type Turn = {
  id: string;
  concept_id: string;
  /**
   * Set on a chapter recap: it belongs to the chapter page, and `concept_id` (the chapter's last section) is only the
   * anchor for section-scoped records.
   */
  chapter_id?: string;
  channel: Channel;
  status: TurnStatus;
  attempt: number;
  /** The last stream event applied to `text`; streamed deltas carry the next one. */
  sequence: number;
  /** The streamed text, and the final text once complete; empty for background channels, which no view shows. */
  text: string;
  error?: string;
  started_at: number;
  source_refs?: Ref[];
  attempts: { attempt: number; text: string; status: TurnStatus }[];
  title?: string | null;
};

/** One step of a stepped lesson (ADR 0009); `turn_id` is set once the step is taught, `replied` once its plan block is read. */
/** A step's check question (ADR 0009): never assessed and never evidence. `correct` indexes `options`. */
export type CheckQuestion = { idea: string; question: string; options: { text: string; explanation: string }[]; correct: number };

/** The learner's choice on a check question: an option's index or "unsure". */
export type CheckChoice = number | 'unsure';

export type CheckAnswer = { choice: CheckChoice; unsure: boolean; correct: boolean; interaction_id: string; answered_at: number };

export type LessonStep = { title: string; added: boolean; turn_id?: string; replied?: boolean; check?: CheckQuestion; answer?: CheckAnswer };

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

/** `images` are attached images (served from /api/images/{name}), sent to the teacher with the question. */
export type QuestionReply = { id: string; question: string; selection: string; images?: string[]; turn_id: string; created_at: number };

export type Question = {
  created_at?: number;
  replies?: QuestionReply[];
  id: string;
  question: string;
  selection: string;
  images?: string[];
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

/** The status of an exercise part after an assessment (ADR 0011). */
export type PartStatus = 'correct' | 'partly_correct' | 'not_yet' | 'not_attempted';

export type PracticeHistory = {
  action: PracticeAction;
  feedback: string;
  /** `passed` exactly when every part is correct. */
  outcome?: 'passed' | 'needs_work';
  /** Each part's status after this assessment; an assessment from before parts has none. */
  parts?: PartStatus[];
  kind?: EvidenceKind;
  answer?: string;
  /** Names of images attached to the answer or question, served from /api/images/{name}. */
  images?: string[];
  /** An ask: the learner's question, answered and never assessed (ADR 0011). */
  question?: string;
};

export type Task = {
  id: string;
  concept_id: string;
  question: string;
  /** What each exercise part asks, in order, optionally with a short label such as "(a)" and, in a review question, the
   * sections the part tests; a task without parts is a single part (ADR 0011). */
  parts?: (string | { label?: string; text: string; concept_ids?: string[] })[];
  /**
   * `review` and `chapter_quiz` are retrieval questions in a review set (`set_id`, ADR 0014). A chapter quiz question
   * belongs to its chapter (`chapter_id`, anchored to the last section), names the sections it tests and, when it asks
   * an earlier exercise again, the exercise it came from.
   */
  origin: 'source' | 'self_created' | 'review' | 'chapter_quiz';
  tests_concept_ids?: string[];
  set_id?: string;
  /** A review question is answered in writing (`apply`) or by choosing one of `options` (`recall`), recorded in `answer`. */
  kind?: 'apply' | 'recall';
  idea?: string;
  options?: CheckQuestion['options'];
  correct?: number;
  answer?: { choice: CheckChoice; correct: boolean; at: number };
  chapter_id?: string;
  quiz_id?: string;
  from_task_id?: string;
  /** The `question` of the section's course exercise the task uses, when it uses one. */
  exercise?: string;
  /** The exercise this one was written like, through Another like this (ADR 0011). */
  variant_of?: string;
  created_at?: number;
  source_refs: Ref[];
  status: 'pending' | 'attempted' | 'deferred' | 'skipped';
  skip_reason?: SkipReason;
  history: PracticeHistory[];
};

export type PracticeAction = 'hint' | 'steps' | 'solution' | 'assess' | 'ask';

export type PracticeJob = {
  answer?: string;
  images?: string[];
  question?: string;
  id: string;
  concept_id: string;
  action: 'generate' | PracticeAction;
  task_id?: string;
  purpose?: 'review' | 'chapter_quiz';
  chapter_id?: string;
  /** The review set a review job writes the questions of (ADR 0014). */
  set_id?: string;
  /** Asking for different exercises: what the learner said should change, and the exercises the new ones replace (ADR 0011). */
  note?: string;
  replaces?: string[];
  /** Another like this: the exercise the new one is written like. */
  variant_of?: string;
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

/** The reasoning efforts Throughline offers, lowest first (Codex's `ultra` is left out); each model offers its own subset. */
export type Effort = 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';

export type Settings = {
  model: string;
  small_model: string;
  effort: Effort;
  small_effort: '' | Effort;
  service_tier: string;
  overridden: boolean;
  path: string;
};

export type UpdateCheck = { version: string; latest: string; available: boolean };

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

/** A course's own presentation preferences. */
export type Preferences = { language: 'en' | 'zh-CN' };

export type State = {
  preferences: Preferences;
  course:{ id: string; title: string };
  position: Position | null;
  sources: { id: string; path: string; revision: string; status: string }[];
  /** `version` changes with any part of the course plan, including fields left out here. */
  curriculum: { version: string; concepts: Concept[]; route: string[]; coverage?: Coverage[]; chapters?: Chapter[] };
  session: { recent_interactions: Interaction[] };
  deferred_explanations: DeferredExplanation[];
  turns: Turn[];
  lessons: SteppedLesson[];
  questions: Question[];
  practice: { tasks: Task[]; jobs: PracticeJob[] };
  preparation: { jobs: PreparationJob[]; next_concept_id: string | null };
  settings: Settings;
  annotations: Annotation[];
  memory: MemoryEntry[];
  skipped: Skipped[];
  builds: ChapterBuild[];
  review: ReviewState;
};

/** A review set (ADR 0014): the questions written for one request, with how many are answered and right. */
export type ReviewSet = {
  id: string;
  kind: 'for_me' | 'request' | 'warm_up' | 'chapter_quiz';
  request?: string;
  scope?: { chapter_ids?: string[]; concept_ids?: string[] };
  /** The section a warm-up comes before, or the chapter a quiz is scoped to. */
  concept_id?: string;
  chapter_id?: string;
  /** What the teacher left out of the request, and why. */
  note?: string;
  created_at: number;
  closed_at?: number;
  task_ids: string[];
  answered: number;
  right: number;
  /** Not closed and some question still unanswered. */
  open: boolean;
};

/** Review sets newest first, review questions and the requests writing them, warm-ups on offer (section id → its stale
 * prerequisites) and how many sections can be reviewed. Chapter quiz questions stay in `practice`. */
export type ReviewState = {
  sets: ReviewSet[];
  reviewable: number;
  warm_ups: Record<string, string[]>;
  tasks: Task[];
  jobs: PracticeJob[];
};

export type AnnotationSource = Ref & { label?: string; page?: number };

/** A course memory entry (ADR 0010); a preference takes effect only once `confirmed`, a difficulty while `active`. */
export type MemoryEntry = {
  id: string;
  kind: 'preference' | 'taught_term' | 'difficulty';
  text: string;
  status: 'suggested' | 'confirmed' | 'active' | 'cleared';
  concept_id: string;
  interaction_ids: string[];
  /** Exercises skipped with the same reason, cited by a preference suggested from them (a skip has no interaction). */
  skip_ids?: string[];
  skip_reason?: SkipReason;
  created_at: number;
  updated_at: number;
};

/** The learner's own highlight, note or bookmark. Never sent to the teacher. */
export type Annotation = {
  id: string;
  kind: 'highlight' | 'note' | 'bookmark';
  concept_id: string;
  turn_id: string | null;
  task_id?: string | null;
  source: AnnotationSource | null;
  passage: string;
  /** Which repeat of the passage in its lesson, answer or exercise; missing means the first. */
  occurrence?: number;
  note: string;
  /** Images on a note; private like the note. */
  images?: string[];
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

export type ChangeScope = 'state' | 'course' | 'library' | 'settings' | 'preferences' | 'preparation' | 'builds' | 'memory';

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
