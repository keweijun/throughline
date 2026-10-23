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
  channel: 'mainline' | 'sidequestion' | 'practice' | 'preparation';
  prompt: string;
  status: TurnStatus;
  attempt: number;
  text: string;
  final_text?: string | null;
  error?: string;
  started_at: number;
  source_refs?: Ref[];
  attempts: { attempt: number; text: string; status: TurnStatus }[];
  metrics: Record<string, number>;
  title?: string | null;
};

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

export type PracticeHistory = {
  action: 'hint' | 'steps' | 'solution' | 'assess';
  feedback: string;
  outcome?: 'passed' | 'needs_work';
  kind?: string;
  answer?: string;
};

export type Task = {
  id: string;
  concept_id: string;
  question: string;
  origin: 'source' | 'self_created';
  source_refs: Ref[];
  status: 'pending' | 'attempted' | 'deferred';
  history: PracticeHistory[];
};

export type PracticeJob = {
  answer?: string;
  id: string;
  concept_id: string;
  action: string;
  task_id?: string;
  processed?: boolean;
  error?: string;
};

export type PreparationJob = {
  id: string;
  concept_id: string;
  status: 'running' | 'ready' | 'deferred' | 'failed' | 'stale';
  reason?: string;
};

export type Settings = {
  model: string;
  effort: 'minimal' | 'low' | 'medium' | 'high';
  overridden: boolean;
  path: string;
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
  curriculum: { concepts: Concept[]; route: string[] };
  session: {
    recent_interactions: Interaction[];
    unanswered_questions: unknown[];
    due_explanations: unknown[];
  };
  deferred_explanations: DeferredExplanation[];
  turns: Turn[];
  questions: Question[];
  practice: { tasks: Task[]; jobs: PracticeJob[] };
  preparation: { jobs: PreparationJob[]; next_concept_id: string | null };
  settings: Settings;
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

export type HostEvent =
  | { type: 'delta'; id: string; attempt: number; text: string }
  | { type: 'turn'; turn: Turn }
  | { type: 'changed'; scope: string };

export type LibraryCourse = {
  name: string;
  path: string;
  title?: string;
  sources?: number;
  concepts?: number;
  needs_review?: number;
  current?: string | null;
  updated?: number;
  error?: string;
};

export type Library = { root: string | null; active: string | null; courses: LibraryCourse[] };
