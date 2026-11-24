import type { MessageKey } from './i18n.svelte';

/** Line icons for Studio's suggestions, each a path in a 20 by 20 field drawn with a thin stroke. */
export const ICONS = {
  exam: 'M3.4 4.6h13.2v11.6H3.4zM3.4 8h13.2M6.8 2.8v3.2M13.2 2.8v3.2M7.6 12.2l1.7 1.6 3.2-3.4',
  book: 'M2.8 4.8c2.5-.9 5-.8 7.2.7 2.2-1.5 4.7-1.6 7.2-.7v10.4c-2.5-.9-5-.8-7.2.7-2.2-1.5-4.7-1.6-7.2-.7zM10 5.5v10.4',
  pencil: 'M3.8 16.2l.8-3.4 8.9-8.9 2.6 2.6-8.9 8.9zM11.9 5.5l2.6 2.6',
  paper: 'M6 2.8h5.4L15 6.4v10.8H6zM11.2 2.8v3.8H15M8.4 10h4.2M8.4 12.8h4.2',
  files: 'M6 2.8h5.4L15 6.4v10.8H6zM11.2 2.8v3.8H15M10.5 9.6v5M8 12.1h5',
  checked: 'M6 2.8h5.4L15 6.4v10.8H6zM11.2 2.8v3.8H15M8.3 12l1.6 1.6 2.8-3.2',
  sliders: 'M3.5 6h6.3M12.8 6h3.7M3.5 14h3.7M10.2 14h6.3M12.8 6a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zM10.2 14a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z',
  section: 'M4 4h12v12H4zM10 7v6M7 10h6',
  sum: 'M14.5 5.4V4h-9l5 6-5 6h9v-1.4',
  code: 'M7.5 6l-4 4 4 4M12.5 6l4 4-4 4',
  cards: 'M4.5 7h9v8.5h-9zM7 4.5h8.5V13',
  globe: 'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM3 10h14M10 3c2.3 2 2.3 12 0 14M10 3c-2.3 2-2.3 12 0 14',
} as const;

/** One thing Studio suggests in an empty chat: its label, the request it starts, and its icon. */
export type Suggestion = { label: MessageKey; request: MessageKey; icon: string };

/**
 * The ways a new course is suggested to begin, on the page it begins on (ADR 0027). Each is something a learner
 * wants to do, so they stand at one level: where the files come from is not a way to begin, since files are dropped
 * whatever the aim. `request` starts the message and leaves the learner to finish it.
 */
export const COURSE_STARTS: Suggestion[] = [
  { label: 'Prepare for an exam', request: 'Make a course for my exam on', icon: ICONS.exam },
  { label: 'Learn a subject', request: 'Make a course from these files. I want to learn', icon: ICONS.book },
  { label: 'Practise problems', request: 'Make a course around these problem sets. I want to be able to solve', icon: ICONS.pencil },
  { label: 'Read a paper', request: 'Make a course that takes me through this paper. I want to understand', icon: ICONS.paper },
];

/** Adding files is always suggested in a course's Studio. */
export const ADD_FILES: Suggestion = { label: 'Add files to this course', request: 'Add these files to {course}:', icon: ICONS.files };

/** Course work Studio can do; a few are drawn each time it opens, so the learner sees its range over time. */
export const COURSE_IDEAS: Suggestion[] = [
  { label: 'Check the pages that still need review', request: 'Review the pages of {course} that still need checking.', icon: ICONS.checked },
  { label: 'Change how this course is taught', request: 'In {course},', icon: ICONS.sliders },
  { label: 'Turn a past exam into practice', request: 'In {course}, turn this past exam into practice in its style:', icon: ICONS.exam },
  { label: 'Add a section the course is missing', request: 'In {course}, add a section on', icon: ICONS.section },
  { label: 'Fill in derivations the notes skip', request: 'In {course}, fill in the derivations my materials skip in chapter', icon: ICONS.sum },
  { label: 'Add Python exercises to a chapter', request: 'In {course}, add Python exercises I can run to chapter', icon: ICONS.code },
  { label: 'Make a one-page cheat sheet', request: 'Make a one-page cheat sheet of {course} as a PDF, covering', icon: ICONS.paper },
  { label: 'Make Anki cards of what I find hard', request: 'Make Anki cards from the difficulties in {course}.', icon: ICONS.cards },
  { label: 'Teach this course in another language', request: 'From now on, teach {course} in', icon: ICONS.globe },
];
