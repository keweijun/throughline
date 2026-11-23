import { t } from './i18n.svelte';
import type { Annotation } from './types';

export function noteLabel(item: Annotation) {
  if (item.kind === 'note') return t('Section note');
  if (item.kind === 'bookmark') return t('Bookmark');
  // A highlight the learner wrote on reads as a note on that passage.
  return item.note ? t('Note') : t('Highlight');
}
