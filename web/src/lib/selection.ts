/** Preserve a single TeX representation for every formula touched by a selection. */
export function selectionMarkdown(selection: Selection, area: HTMLElement): string {
  const range = selection.getRangeAt(0).cloneRange();
  // Expand partial formula endpoints before cloning, so MathML/glyph duplication never leaks.
  const formulas = [...area.querySelectorAll<HTMLElement>('[data-tex]')].filter((node) => range.intersectsNode(node));
  const first = formulas[0], last = formulas.at(-1);
  if (first?.contains(range.startContainer)) range.setStartBefore(first);
  if (last?.contains(range.endContainer)) range.setEndAfter(last);
  const fragment = range.cloneContents();
  for (const formula of fragment.querySelectorAll<HTMLElement>('[data-tex]')) {
    const tex = formula.dataset.tex ?? '';
    const delimiter = formula.querySelector('.katex-display') || tex.includes('\n') ? '$$' : '$';
    formula.replaceWith(document.createTextNode(`${delimiter}${tex}${delimiter}`));
  }
  for (const block of fragment.querySelectorAll('p,div,li,blockquote,tr,h1,h2,h3,h4')) block.append(document.createTextNode('\n'));
  return (fragment.textContent ?? '').trim();
}
