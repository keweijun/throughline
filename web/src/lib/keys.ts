/**
 * Enter sends; Shift+Enter or Ctrl+Enter inserts a line break.
 * Without a callback, Enter submits the textarea's form unless its submit button is disabled.
 */
export function enterToSend(node: HTMLTextAreaElement, send?: () => void) {
  let callback = send;

  function onKeydown(event: KeyboardEvent) {
    if (event.key !== 'Enter' || event.isComposing || event.altKey) return;
    event.preventDefault();
    if (event.shiftKey || event.ctrlKey) return insertLineBreak();
    if (callback) return callback();
    const form = node.form;
    const submit = form?.querySelector<HTMLButtonElement>('button[type="submit"], button:not([type])');
    if (form && !submit?.disabled) form.requestSubmit(submit ?? undefined);
  }

  function insertLineBreak() {
    // execCommand keeps native undo and fires `input`, so bound values update.
    if (document.execCommand('insertText', false, '\n')) return;
    node.setRangeText('\n', node.selectionStart, node.selectionEnd, 'end');
    node.dispatchEvent(new Event('input', { bubbles: true }));
  }

  node.addEventListener('keydown', onKeydown);
  return {
    update(next?: () => void) {
      callback = next;
    },
    destroy() {
      node.removeEventListener('keydown', onKeydown);
    },
  };
}
