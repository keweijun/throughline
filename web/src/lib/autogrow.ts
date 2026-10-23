/**
 * Grows a textarea with its text, from its `rows` up to the CSS max-height (then it scrolls), in place of a drag
 * handle. Pass the bound value so changes made in code, such as clearing after sending or restoring a draft, resize
 * it too.
 */
export function autogrow(node: HTMLTextAreaElement, _value?: string) {
  const fit = () => {
    // Hidden fields (a closed disclosure, an inactive tab) measure as empty; they keep their rows until shown and edited.
    if (!node.offsetParent) return;
    node.style.height = 'auto';
    node.style.height = `${node.scrollHeight + node.offsetHeight - node.clientHeight}px`;
  };
  node.addEventListener('input', fit);
  requestAnimationFrame(fit);
  return {
    update() {
      requestAnimationFrame(fit);
    },
    destroy() {
      node.removeEventListener('input', fit);
    },
  };
}
