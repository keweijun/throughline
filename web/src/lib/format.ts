import { t, type MessageKey } from './i18n.svelte';
import type { EvidenceKind, PartStatus, PracticeAction, Question, Task, TurnStatus } from './types';

type Tone = 'good' | 'caution' | 'danger' | 'accent' | 'plain';

// Labels are message keys, so a label without a translation fails the type check.

export const lessonStatus: Record<TurnStatus, { label: MessageKey; tone: Tone }> = {
  running: { label: 'Writing', tone: 'accent' },
  completed: { label: 'Saved', tone: 'plain' },
  paused: { label: 'Paused · unfinished', tone: 'caution' },
  interrupted: { label: 'Interrupted · unfinished', tone: 'caution' },
  failed: { label: 'Failed · unfinished', tone: 'danger' },
};

export const verification = (value: string | undefined): { label: MessageKey; tone: Tone } =>
  value === 'verified' ? { label: 'Verified', tone: 'good' } : { label: 'Pending verification', tone: 'caution' };

export const helpLabels: Record<PracticeAction, MessageKey> = {
  hint: 'Hint',
  steps: 'Key steps',
  solution: 'Full solution',
  assess: 'Teacher feedback',
  ask: 'Question',
};

const evidenceLabels: Record<EvidenceKind, MessageKey> = {
  independent: 'Solved independently',
  retest_passed: 'Remembered on your own',
  hinted: 'Solved with help',
  needs_work: 'Needs another try',
};

/** The learner-facing name of an evidence kind; an unknown kind from a newer host shows as is. */
export const evidenceLabel = (kind: string) => (Object.hasOwn(evidenceLabels, kind) ? t(evidenceLabels[kind as EvidenceKind]) : kind);

/** How the teacher placed a side question on the route. */
const questionCategories: Record<string, MessageKey> = {
  local: 'about this passage',
  prerequisite: 'a missing foundation',
  future: 'covered fully later',
  repeated: 'a repeated difficulty',
  extension: 'an extension',
};

export const questionCategory = (category: string) =>
  Object.hasOwn(questionCategories, category) ? t(questionCategories[category]) : category;

/** Each part's status after the latest assessment; an assessment from before parts gave its one part's status (ADR 0011). */
export const partStatuses = (task: Task): PartStatus[] => {
  const count = task.parts?.length || 1;
  const last = task.history.filter((h) => h.action === 'assess').at(-1);
  if (last?.parts?.length === count) return last.parts;
  if (last && count === 1) return [last.outcome === 'passed' ? 'correct' : 'not_yet'];
  return Array(count).fill('not_attempted');
};

/** An exercise is solved when every part is correct. */
export const solved = (task: Task) => partStatuses(task).every((s) => s === 'correct');

export const partLabels: Record<PartStatus, { label: MessageKey; tone: Tone }> = {
  correct: { label: 'Correct', tone: 'good' },
  partly_correct: { label: 'Partly correct', tone: 'accent' },
  not_yet: { label: 'Not yet', tone: 'caution' },
  not_attempted: { label: 'Not attempted', tone: 'plain' },
};

/** Every turn that answers a side question: the answer, a foundation supplement and follow-up replies. */
export const questionTurnIds = (question: Question) =>
  [question.turn_id, question.supplement_turn_id, ...(question.replies ?? []).map((r) => r.turn_id)].filter((id): id is string => !!id);
