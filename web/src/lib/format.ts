import { t, type MessageKey } from './i18n.svelte';
import type { EvidenceKind, PracticeAction, Question, Task, TurnStatus } from './types';

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
};

const evidenceLabels: Record<EvidenceKind, MessageKey> = {
  independent: 'Solved independently',
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

export const solved = (task: Task) => task.history.filter((h) => h.action === 'assess').at(-1)?.outcome === 'passed';

/** Every turn that answers a side question: the answer, a foundation supplement and follow-up replies. */
export const questionTurnIds = (question: Question) =>
  [question.turn_id, question.supplement_turn_id, ...(question.replies ?? []).map((r) => r.turn_id)].filter((id): id is string => !!id);
