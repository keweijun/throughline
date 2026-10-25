/** Below this width the side panel covers the reading column instead of sitting beside it (the same breakpoint as the CSS). */
const NARROW = '(max-width: 79.99rem)';

/** True when the side panel overlays the lesson, so it should get out of the way after sending the learner there. */
export function panelCoversLesson() {
  return matchMedia(NARROW).matches;
}
