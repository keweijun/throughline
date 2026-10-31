import katex from 'katex';
import { Compartment, EditorState, Prec, type Extension } from '@codemirror/state';
import { EditorView, keymap, placeholder as hint } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import {
  acceptCompletion,
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  snippet,
  snippetCompletion,
  type Completion,
  type CompletionContext,
} from '@codemirror/autocomplete';
import vocabulary from './latex-vocabulary.json';

/**
 * The text field of every writing box: CodeMirror with LaTeX completion. Typing `\` suggests the commands KaTeX renders
 * (lib/latex-vocabulary.json, built from KaTeX by scripts/latex-vocabulary.mjs); Tab or Enter takes one, and a command
 * with arguments leaves its braces as fields that Tab moves through. `\begin{` suggests environments.
 */

// Ranked above the rest when they match equally well; the vocabulary itself is alphabetical.
const COMMON = new Set(['frac', 'sqrt', 'int', 'sum', 'prod', 'lim', 'infty', 'partial', 'nabla', 'cdot', 'times', 'leq', 'geq', 'neq',
  'approx', 'to', 'mathbb', 'mathrm', 'text', 'vec', 'hat', 'bar', 'dot', 'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'theta',
  'lambda', 'mu', 'pi', 'sigma', 'phi', 'omega', 'Delta', 'Omega', 'sin', 'cos', 'tan', 'log', 'ln', 'exp', 'in', 'pm', 'cdots',
  'ldots', 'binom', 'dfrac', 'overline', 'mathbf', 'operatorname', 'Rightarrow', 'iff', 'forall', 'exists']);

const ARGS = ['a', 'b', 'c'];
const SAMPLE_ROWS = 'a & b \\\\ c & d';

/** A rendered sample of a completion, shown beside the list. */
function sample(tex: string, display = false) {
  return () => {
    const node = document.createElement('div');
    node.className = 'latex-sample';
    try {
      katex.render(tex, node, { throwOnError: true, displayMode: display });
    } catch {
      return null;
    }
    return node;
  };
}

// Only `${` starts a field in a snippet template, so the braces around one need no escaping. They are left bare on
// purpose: @codemirror/autocomplete 6.20.4 misplaces the fields after several escaped braces on one line, and the
// snippet then throws on the next keystroke.
const braces = (count: number) => Array.from({ length: count }, (_, i) => `{\${${i + 1}}}`).join('');

const commands: Completion[] = [
  ...(vocabulary.commands as [string, number][]).map(([name, arity]) => {
    const option: Completion = {
      label: `\\${name}`,
      detail: '{}'.repeat(arity),
      boost: COMMON.has(name) ? 2 : 0,
      info: sample(`\\${name}${ARGS.slice(0, arity).map((a) => `{${a}}`).join('')}`),
    };
    return arity ? snippetCompletion(`\\${name}${braces(arity)}\${0}`, option) : option;
  }),
  // `\left\{` has a literal escaped brace, which a snippet template cannot hold reliably (see above); the cursor
  // simply lands between the delimiters.
  ...[['(', ')'], ['[', ']'], ['\\{', '\\}'], ['|', '|']].map(([open, close]): Completion => ({
    label: `\\left${open}`,
    displayLabel: `\\left${open} … \\right${close}`,
    boost: 1,
    info: sample(`\\left${open} \\frac{a}{b} \\right${close}`),
    apply: (view, _completion, from, to) => {
      const head = `\\left${open} `;
      view.dispatch({
        changes: { from, to, insert: `${head} \\right${close}` },
        selection: { anchor: from + head.length },
        userEvent: 'input.complete',
      });
    },
  })),
  snippetCompletion('\\begin{${1:matrix}}\n\t${2}\n\\end{${1:matrix}}${0}', {
    label: '\\begin',
    detail: '{…}',
    boost: 1,
    info: sample(`\\begin{matrix}${SAMPLE_ROWS}\\end{matrix}`, true),
  }),
];

const environments: Completion[] = vocabulary.environments.map((name) => {
  const head = name.startsWith('array') || name.startsWith('darray') || name.startsWith('subarray') ? '{cc}' : name.startsWith('alignat') || name === 'alignedat' ? '{2}' : '';
  const insert = snippet(`${name}}${head}\n\t\${1}\n\\end{${name}}\${0}`);
  return {
    label: name,
    // Typing `\begin{` closes its brace; the environment's own `}` replaces that one.
    apply: (view, completion, from, to) => insert(view, completion, from, view.state.sliceDoc(to, to + 1) === '}' ? to + 1 : to),
    info: sample(`\\begin{${name}}${head}${SAMPLE_ROWS}\\end{${name}}`, true),
  };
});

function latex(context: CompletionContext) {
  const environment = context.matchBefore(/\\begin\{[A-Za-z]*\*?/);
  if (environment) return { from: environment.from + '\\begin{'.length, options: environments, validFor: /^[A-Za-z]*\*?$/ };
  const word = context.matchBefore(/\\[A-Za-z]*/);
  // `\\` is a line break in math, not the start of a command.
  if (!word || context.state.sliceDoc(word.from - 1, word.from) === '\\') return null;
  return { from: word.from, options: commands, validFor: /^\\[A-Za-z]*$/ };
}

export type EditorOptions = {
  value: string;
  id?: string;
  label: string;
  placeholder: string;
  describedBy?: string;
  /** The height it starts at, in lines; it grows with the text up to the CSS max-height, then scrolls. */
  rows?: number;
  onchange: (value: string) => void;
  onsend: () => void;
  oncancel?: () => void;
  /** Pasted content; return true when it was taken, such as images being attached. */
  onpaste?: (event: ClipboardEvent) => boolean;
};

function extensions(options: () => EditorOptions, placeholder: Compartment): Extension[] {
  const initial = options();
  return [
    history(),
    EditorView.lineWrapping,
    placeholder.of(hint(initial.placeholder)),
    // Only brackets pair up: quotes and dollar signs are as often prose (an apostrophe, a price) as math.
    EditorState.languageData.of(() => [{ closeBrackets: { brackets: ['(', '[', '{'] } }]),
    closeBrackets(),
    autocompletion({ override: [latex], icons: false, maxRenderedOptions: 60 }),
    Prec.highest(
      keymap.of([
        { key: 'Mod-Enter', run: () => (options().onsend(), true) },
        { key: 'Tab', run: acceptCompletion },
      ]),
    ),
    Prec.high(keymap.of([{ key: 'Escape', run: () => (options().oncancel ? (options().oncancel!(), true) : false) }])),
    keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap]),
    EditorView.contentAttributes.of(() => {
      const { id, label, describedBy } = options();
      return { 'aria-label': label, 'aria-multiline': 'true', ...(id ? { id } : {}), ...(describedBy ? { 'aria-describedby': describedBy } : {}) };
    }),
    EditorView.domEventHandlers({ paste: (event) => options().onpaste?.(event) ?? false }),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) options().onchange(update.state.doc.toString());
    }),
    EditorView.theme({ '.cm-content': { minHeight: `${(initial.rows ?? 2) * 1.5}em` } }),
  ];
}

/** A Svelte action that puts the editor in `node`, kept in step with `value` when it is changed elsewhere (a draft cleared after sending). */
export function editor(node: HTMLElement, initial: EditorOptions) {
  let options = initial;
  // The placeholder says what the box writes to, which changes with it (a new question, a follow-up).
  const placeholder = new Compartment();
  const view = new EditorView({
    parent: node,
    state: EditorState.create({ doc: initial.value, extensions: extensions(() => options, placeholder) }),
  });
  return {
    update(next: EditorOptions) {
      const changed = next.id !== options.id || next.label !== options.label || next.describedBy !== options.describedBy;
      if (next.placeholder !== options.placeholder) view.dispatch({ effects: placeholder.reconfigure(hint(next.placeholder)) });
      options = next;
      if (next.value !== view.state.doc.toString()) {
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: next.value } });
      }
      // Attributes are read from the options when the view updates; an empty transaction makes it read them again.
      if (changed) view.dispatch({});
    },
    destroy() {
      view.destroy();
    },
  };
}
