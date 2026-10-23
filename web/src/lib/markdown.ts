import { t, locale, type Language } from './i18n.svelte';
import DOMPurify from 'dompurify';
import katex from 'katex';
import { marked } from 'marked';
import type { Ref } from './types';

const MATH = /(```[\s\S]*?```|`[^`\n]*`)|(\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\\\(([\s\S]+?)\\\)|\$([^$\n]+?)\$)/g;
const CITATION = /\[(?:Source|来源)\s+([^\s/\]]+)\s*\/\s*([^\]\s]+)\]/g;
const DECISION = /<teaching-decision>[\s\S]*$/;

function parse(text: string, breaks = false): DocumentFragment {
  const math: { tex: string; display: boolean }[] = [];
  const token = 'MATH' + crypto.randomUUID().replaceAll('-', '');
  const prepared = text.replace(MATH, (whole, code, _expr, a, b, c, d) => {
    if (code) return code;
    math.push({ tex: a ?? b ?? c ?? d, display: a !== undefined || b !== undefined });
    return token + (math.length - 1) + 'END';
  });
  const fragment = DOMPurify.sanitize(marked.parse(prepared, { async: false, breaks }) as string, {
    RETURN_DOM_FRAGMENT: true,
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'style', 'iframe', 'form', 'input', 'button', 'video', 'audio'],
    FORBID_ATTR: ['style', 'id'],
    ALLOW_DATA_ATTR: false,
  });
  replaceText(fragment, new RegExp(token + '(\\d+)END', 'g'), (match) => {
    const item = math[Number(match[1])];
    const span = document.createElement('span');
    span.dataset.tex = item.tex;
    try {
      katex.render(item.tex, span, { displayMode: item.display, throwOnError: false, trust: false, maxExpand: 1000, maxSize: 20 });
    } catch {
      span.textContent = item.tex;
    }
    return span;
  });
  for (const link of fragment.querySelectorAll('a')) {
    const href = link.getAttribute('href') ?? '';
    if (!/^(https?:\/\/|#)/i.test(href)) link.removeAttribute('href');
    else {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
  }
  return fragment;
}

function replaceText(root: Node, pattern: RegExp, build: (match: RegExpExecArray) => Node, skip = 'code,pre,.katex') {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  while (walker.nextNode()) {
    const node = walker.currentNode as Text;
    if (!node.parentElement?.closest(skip)) texts.push(node);
  }
  for (const node of texts) {
    const value = node.textContent ?? '';
    const result = document.createDocumentFragment();
    let last = 0;
    let match: RegExpExecArray | null;
    pattern.lastIndex = 0;
    while ((match = pattern.exec(value))) {
      result.append(value.slice(last, match.index), build(match));
      last = pattern.lastIndex;
    }
    if (last) {
      result.append(value.slice(last));
      node.replaceWith(result);
    }
  }
}

function linkCitations(fragment: DocumentFragment, refs: Ref[], onSource?: (ref: Ref) => void) {
  replaceText(fragment, CITATION, (match) => {
    const ref = refs.find((r) => r.source_id === match[1] && r.unit_id === match[2]);
    if (!ref || !onSource) {
      const pending = document.createElement('span');
      pending.className = 'citation citation-missing';
      pending.title = t('This citation does not match a registered source location');
      pending.textContent = t('source unverified');
      return pending;
    }
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'citation';
    button.dataset.ref = JSON.stringify(ref);
    button.textContent = labelFor(ref);
    button.title = t('Open the cited source');
    button.setAttribute('aria-label', t('View source {location}', { location: labelFor(ref) }));
    button.addEventListener('click', () => onSource(ref));
    return button;
  });
}

export function labelFor(ref: Ref) {
  const page = ref.unit_id.match(/^page-(\d+)$/);
  const line = ref.unit_id.match(/^line-(\d+)$/);
  return page ? t('p. {number}', { number: page[1] }) : line ? t('line {number}', { number: line[1] }) : ref.unit_id;
}

export type MarkdownOptions = { language?: Language; text: string; breaks?: boolean; refs?: Ref[]; onSource?: (ref: Ref) => void };

/** Renders sanitized Markdown, patching only changed blocks so streaming keeps selections and scroll. */
export function render(node: HTMLElement, { text, breaks = false, refs = [], onSource }: MarkdownOptions) {
  const key = locale.language + breaks + text + '\u0000' + refs.map((r) => r.source_id + r.unit_id).join();
  if (node.dataset.key === key) return;
  const fragment = parse(text.replace(DECISION, ''), breaks);
  linkCitations(fragment, refs, onSource);
  const scrollY = window.scrollY;
  const incoming = [...fragment.childNodes];
  incoming.forEach((child, index) => {
    const old = node.childNodes[index];
    if (!old) node.append(child);
    else if (!old.isEqualNode(child)) old.replaceWith(child);
  });
  while (node.childNodes.length > incoming.length) node.lastChild!.remove();
  node.dataset.key = key;
  if (window.scrollY !== scrollY) window.scrollTo(window.scrollX, scrollY);
}

export function markdown(node: HTMLElement, options: MarkdownOptions) {
  render(node, options);
  return { update: (next: MarkdownOptions) => render(node, next) };
}
