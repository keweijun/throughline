import type { Task, TurnStatus } from './types';

type Tone = 'good' | 'caution' | 'danger' | 'accent' | 'plain';

export const lessonStatus: Record<TurnStatus, { label: string; tone: Tone }> = {
  running: { label: 'Writing', tone: 'accent' },
  completed: { label: 'Saved', tone: 'plain' },
  paused: { label: 'Paused · unfinished', tone: 'caution' },
  interrupted: { label: 'Interrupted · unfinished', tone: 'caution' },
  failed: { label: 'Failed · unfinished', tone: 'danger' },
};

export const verification = (value: string | undefined) =>
  value === 'verified' ? { label: 'Verified', tone: 'good' as Tone } : { label: 'Pending verification', tone: 'caution' as Tone };

export const helpLabels: Record<string, string> = {
  hint: 'Hint',
  steps: 'Key steps',
  solution: 'Full solution',
  assess: 'Teacher feedback',
};

export const evidenceLabels: Record<string, string> = {
  independent: 'Solved independently',
  hinted: 'Solved with help',
  needs_work: 'Needs another try',
};

export const solved = (task: Task) => task.history.filter((h) => h.action === 'assess').at(-1)?.outcome === 'passed';
