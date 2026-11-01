/**
 * Draws the eye to a control: Help's "Show me" scrolls it into view and rings it for a few seconds where it already
 * is, so the learner learns where a thing lives instead of being taken there.
 */
export function spotlight(selector: string) {
  const element = document.querySelector<HTMLElement>(selector);
  if (!element || !element.getClientRects().length) return false;
  element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  element.classList.remove('spotlit');
  // Restarting the animation needs a style flush between removing and adding the class.
  void element.offsetWidth;
  element.classList.add('spotlit');
  setTimeout(() => element.classList.remove('spotlit'), 2700);
  return true;
}

/** Whether the control is on screen now, so Help offers "Show me" only for what it can point at. */
export function shown(selector: string) {
  return !!document.querySelector<HTMLElement>(selector)?.getClientRects().length;
}
