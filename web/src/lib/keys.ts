/**
 * Every writing box sends the same way, since questions, notes and answers all run to several lines of math: Enter
 * inserts a line break and Ctrl+Enter (Cmd+Enter on a Mac) sends.
 */
export function modEnterToSend(node: HTMLTextAreaElement, send: () => void) {
  let callback = send;

  function onKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter' || event.isComposing || !(event.ctrlKey || event.metaKey)) return;
    event.preventDefault();
    callback();
  }

  node.addEventListener('keydown', onKeydown);
  return {
    update(next: () => void) {
      callback = next;
    },
    destroy() {
      node.removeEventListener('keydown', onKeydown);
    },
  };
}

/** The keys that send with modEnterToSend on this computer. */
export const sendKeys = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ Enter' : 'Ctrl+Enter';
