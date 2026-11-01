import katex from 'katex';
import { Compartment, EditorState, Prec, StateEffect, StateField, type Extension } from '@codemirror/state';
import { Decoration, EditorView, keymap, placeholder as hint, type DecorationSet } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import {
  acceptCompletion,
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  snippet,
  type Completion,
  type CompletionContext,
  type CompletionSource,
} from '@codemirror/autocomplete';
import { linter, type Diagnostic } from '@codemirror/lint';
import { inMath, mathSpans } from './markdown';
import { chemistryReady } from './widgets';
import vocabulary from './latex-vocabulary.json';

/**
 * The text field of every writing box: CodeMirror with LaTeX completion. Typing `\` suggests the commands KaTeX renders
 * (lib/latex-vocabulary.json, built from KaTeX by scripts/latex-vocabulary.mjs); Tab or Enter takes one, and a command
 * with arguments leaves its braces as fields that Tab moves through. `\begin{` suggests environments. A suggestion taken
 * outside math is wrapped in `$…$` (`$$…$$` for an environment) so it renders, and what KaTeX cannot render in a formula
 * is underlined with KaTeX's message.
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

type Apply = Exclude<Completion['apply'], string | undefined>;

/**
 * Takes a suggestion in math as it is, and outside math wraps it so it renders: `$…$` for a command, `$$…$$` for an
 * environment. Inside the wrapping the cursor stays in the formula, so it can go on; one more Tab leaves it.
 */
function wrapped(inside: string, outside: string): Apply {
  const plain = snippet(inside);
  const wrap = snippet(outside);
  return (view, completion, from, to) => (inMath(view.state.doc.toString(), from) ? plain : wrap)(view, completion, from, to);
}

const commands: Completion[] = [
  ...(vocabulary.commands as [string, number][]).map(([name, arity]): Completion => ({
    label: `\\${name}`,
    detail: '{}'.repeat(arity),
    boost: COMMON.has(name) ? 2 : 0,
    info: sample(`\\${name}${ARGS.slice(0, arity).map((a) => `{${a}}`).join('')}`),
    apply: wrapped(`\\${name}${braces(arity)}\${0}`, `$\\${name}${braces(arity)}\${${arity + 1}}$\${0}`),
  })),
  // `\left\{` has a literal escaped brace, which a snippet template cannot hold reliably (see above); the cursor
  // simply lands between the delimiters.
  ...[['(', ')'], ['[', ']'], ['\\{', '\\}'], ['|', '|']].map(([open, close]): Completion => ({
    label: `\\left${open}`,
    displayLabel: `\\left${open} … \\right${close}`,
    boost: 1,
    info: sample(`\\left${open} \\frac{a}{b} \\right${close}`),
    apply: (view, _completion, from, to) => {
      const dollar = inMath(view.state.doc.toString(), from) ? '' : '$';
      const head = `${dollar}\\left${open} `;
      view.dispatch({
        changes: { from, to, insert: `${head} \\right${close}${dollar}` },
        selection: { anchor: from + head.length },
        userEvent: 'input.complete',
      });
    },
  })),
  {
    label: '\\begin',
    detail: '{…}',
    boost: 1,
    info: sample(`\\begin{matrix}${SAMPLE_ROWS}\\end{matrix}`, true),
    apply: wrapped('\\begin{${1:matrix}}\n\t${2}\n\\end{${1:matrix}}${0}', '$$\\begin{${1:matrix}}\n\t${2}\n\\end{${1:matrix}}$$${0}'),
  },
];

const environments: Completion[] = vocabulary.environments.map((name) => {
  const head = name.startsWith('array') || name.startsWith('darray') || name.startsWith('subarray') ? '{cc}' : name.startsWith('alignat') || name === 'alignedat' ? '{2}' : '';
  const inside = snippet(`${name}}${head}\n\t\${1}\n\\end{${name}}\${0}`);
  const outside = snippet(`${name}}${head}\n\t\${1}\n\\end{${name}}$$\${0}`);
  return {
    label: name,
    info: sample(`\\begin{${name}}${head}${SAMPLE_ROWS}\\end{${name}}`, true),
    apply: (view, completion, from, to) => {
      // Typing `\begin{` closes its brace; the environment's own `}` replaces that one.
      const end = view.state.sliceDoc(to, to + 1) === '}' ? to + 1 : to;
      const begin = from - '\\begin{'.length;
      if (inMath(view.state.doc.toString(), begin)) return inside(view, completion, from, end);
      // Outside math the environment becomes display math: `$$` before `\begin`, and after `\end` with the rest.
      view.dispatch({ changes: { from: begin, insert: '$$' } });
      outside(view, completion, from + 2, end + 2);
    },
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

/** Underlines what KaTeX cannot render in each closed formula, where it fails, with KaTeX's own message. */
const formulaCheck = linter(
  (view) => {
    const found: Diagnostic[] = [];
    for (const span of mathSpans(view.state.doc.toString())) {
      // Chemistry renders once mhchem has loaded; until then it is not an error.
      if (!chemistryReady(span.tex)) continue;
      try {
        katex.renderToString(span.tex, { displayMode: span.display, throwOnError: true, trust: false, maxExpand: 1000, maxSize: 20 });
      } catch (error) {
        if (!(error instanceof katex.ParseError)) continue;
        const end = span.from + span.tex.length;
        // An error at the very end (an unclosed brace) marks the last character, so there is something to underline.
        const from = Math.min(span.from + (error.position ?? 0), end - 1);
        found.push({ from, to: Math.min(Math.max(from + (error.length || 1), from + 1), end), severity: 'error', source: 'KaTeX', message: error.rawMessage || error.message });
      }
    }
    return found;
  },
  { delay: 500 },
);

/**
 * A chip: a skill (`$name`) or a file (`@path`) in Studio's box, as in Codex's own composer. It is one piece of the
 * text that the cursor steps over and Backspace removes whole, and it remembers what it names, so a file name with
 * spaces still names one file.
 */
export type Chip = { kind: 'skill' | 'mention'; name: string; path: string };
export type ChipRange = { from: number; to: number; chip: Chip };

const addChip = StateEffect.define<ChipRange>({ map: (value, change) => ({ ...value, from: change.mapPos(value.from), to: change.mapPos(value.to) }) });

const chips = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(set, transaction) {
    set = set.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (effect.is(addChip) && effect.value.to > effect.value.from) {
        const { from, to, chip } = effect.value;
        set = set.update({ add: [Decoration.mark({ class: `cm-chip cm-chip-${chip.kind}`, chip }).range(from, to)] });
      }
    }
    return set;
  },
  provide: (field) => [EditorView.decorations.from(field), EditorView.atomicRanges.of((view) => view.state.field(field))],
});

/** The chips in the text, in order. */
export function chipsOf(state: EditorState): ChipRange[] {
  const found: ChipRange[] = [];
  state.field(chips, false)?.between(0, state.doc.length, (from, to, value) => {
    found.push({ from, to, chip: value.spec.chip as Chip });
  });
  return found;
}

/** Puts a chip with `label` (and a space after it) in place of `from`–`to`, the cursor after it. */
export function insertChip(view: EditorView, chip: Chip, label: string, from = view.state.selection.main.head, to = from) {
  const before = from > 0 && !/\s/.test(view.state.sliceDoc(from - 1, from)) ? ' ' : '';
  const start = from + before.length;
  view.dispatch({
    changes: { from, to, insert: `${before}${label} ` },
    effects: addChip.of({ from: start, to: start + label.length, chip }),
    selection: { anchor: start + label.length + 1 },
    userEvent: 'input.complete',
  });
  view.focus();
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
  /** More suggestions beside LaTeX, fixed when the editor is made: Studio's `$` skills and `@` files. */
  completions?: CompletionSource[];
  /** Called with the chips whenever they change. */
  onchips?: (chips: ChipRange[]) => void;
  /** The up arrow in an empty box puts back what this returns, as Codex recalls the last message. */
  onrecall?: () => string | null;
  /** Hands over the editor, for inserting chips from outside it (an attached file). */
  onview?: (view: EditorView) => void;
};

/**
 * The editor in the app's own look, from the design tokens in app.css: the field is bare inside the composer's frame,
 * and the suggestion list, its rendered sample and the formula check's message are popovers like the selection
 * toolbar (SelectionAsk): raised, rounded, shadowed, rows that wash with the accent. A theme outranks CodeMirror's own
 * base styles, so nothing here needs !important.
 */
const popover = {
  border: '1px solid var(--rule-strong)',
  borderRadius: '8px',
  background: 'var(--raised)',
  color: 'var(--ink)',
  boxShadow: 'var(--shadow)',
  fontFamily: 'var(--sans)',
  animation: 'enter-pop var(--quick) var(--ease-out)',
};

const look = EditorView.theme({
  '&': { fontSize: 'var(--step-0)', lineHeight: '1.5', color: 'var(--ink)', backgroundColor: 'transparent' },
  '&.cm-focused': { outline: 'none' },
  // It grows with the text, then scrolls, like the text areas it replaced.
  '.cm-scroller': { maxHeight: '18rem', overflowY: 'auto', fontFamily: 'var(--sans)', lineHeight: 'inherit' },
  '.cm-content': { padding: '0.6rem 0.8rem 0.3rem', caretColor: 'var(--ink)' },
  '.cm-line': { padding: '0' },
  '.cm-placeholder': { color: 'var(--pencil)', opacity: '0.75' },

  // A snippet's fields: where Tab goes next.
  '.cm-snippetField': { backgroundColor: 'var(--accent-wash)', borderRadius: '3px', boxShadow: '0 0 0 1px var(--accent-wash)' },
  '.cm-snippetFieldPosition': { borderLeft: '1.5px solid var(--accent)', margin: '0 -0.75px -0.2em' },

  '.cm-tooltip': { ...popover },

  // The suggestion list: a command in the code face, what it takes beside it, the row in reach washed with the accent.
  '.cm-tooltip.cm-tooltip-autocomplete': { padding: '0.25rem' },
  '.cm-tooltip.cm-tooltip-autocomplete > ul': { fontFamily: 'var(--sans)', maxHeight: '15rem', minWidth: '11rem' },
  '.cm-tooltip.cm-tooltip-autocomplete > ul > li': {
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.6rem',
    padding: '0.3rem 0.55rem',
    borderRadius: '6px',
    color: 'var(--ink)',
    lineHeight: '1.3',
  },
  '.cm-tooltip.cm-tooltip-autocomplete > ul > li[aria-selected]': { backgroundColor: 'var(--accent-wash)', color: 'var(--accent)' },
  '.cm-completionLabel': { fontFamily: 'var(--mono)', fontSize: 'var(--step--1)' },
  '.cm-completionMatchedText': { textDecoration: 'none', fontWeight: '700' },
  '.cm-completionDetail': { marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: '0.75rem', fontStyle: 'normal', color: 'var(--pencil)' },

  // The rendered sample of the suggestion in reach, a card of its own beside the list.
  '.cm-tooltip.cm-completionInfo': { padding: '0.6rem 0.85rem', margin: '0 0.35rem', maxWidth: '20rem' },
  '.cm-completionInfo .latex-sample': { fontSize: '1.15rem' },

  // The formula check's message: what KaTeX could not render, marked like the app's other errors.
  '.cm-lintRange-error': {
    backgroundImage: 'none',
    textDecoration: 'underline wavy var(--danger)',
    textDecorationSkipInk: 'none',
    textUnderlineOffset: '3px',
  },
  '.cm-tooltip.cm-tooltip-lint': { padding: '0.25rem' },
  '.cm-diagnostic': { padding: '0.35rem 0.6rem', borderLeft: 'none', borderRadius: '6px', fontSize: 'var(--step--1)', whiteSpace: 'normal' },
  '.cm-diagnostic-error': { borderLeft: 'none', backgroundColor: 'var(--danger-wash)', color: 'var(--danger)' },
  '.cm-diagnosticSource': { display: 'block', marginTop: '0.15rem', fontSize: '0.75rem', color: 'var(--pencil)', opacity: '1' },

  // A chip: a skill or file named in the text, set off like a tag; skills take the accent, files the pencil.
  '.cm-chip': { padding: '0.05rem 0.3rem', borderRadius: '5px', fontFamily: 'var(--mono)', fontSize: '0.92em' },
  '.cm-chip-skill': { backgroundColor: 'var(--accent-wash)', color: 'var(--accent)' },
  '.cm-chip-mention': { backgroundColor: 'var(--rule)', color: 'var(--ink-soft)' },
});

function extensions(options: () => EditorOptions, placeholder: Compartment): Extension[] {
  const initial = options();
  return [
    history(),
    EditorView.lineWrapping,
    placeholder.of(hint(initial.placeholder)),
    // Only brackets pair up: quotes and dollar signs are as often prose (an apostrophe, a price) as math.
    EditorState.languageData.of(() => [{ closeBrackets: { brackets: ['(', '[', '{'] } }]),
    closeBrackets(),
    autocompletion({ override: [latex, ...(initial.completions ?? [])], icons: false, maxRenderedOptions: 60 }),
    formulaCheck,
    chips,
    Prec.highest(
      keymap.of([
        { key: 'Mod-Enter', run: () => (options().onsend(), true) },
        { key: 'Tab', run: acceptCompletion },
      ]),
    ),
    Prec.high(keymap.of([{ key: 'Escape', run: () => (options().oncancel ? (options().oncancel!(), true) : false) }])),
    Prec.high(
      keymap.of([
        {
          key: 'ArrowUp',
          run: (view) => {
            const recalled = view.state.doc.length === 0 ? options().onrecall?.() : null;
            if (!recalled) return false;
            view.dispatch({ changes: { from: 0, insert: recalled }, selection: { anchor: recalled.length } });
            return true;
          },
        },
      ]),
    ),
    keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap]),
    EditorView.contentAttributes.of(() => {
      const { id, label, describedBy } = options();
      return { 'aria-label': label, 'aria-multiline': 'true', ...(id ? { id } : {}), ...(describedBy ? { 'aria-describedby': describedBy } : {}) };
    }),
    EditorView.domEventHandlers({ paste: (event) => options().onpaste?.(event) ?? false }),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) options().onchange(update.state.doc.toString());
      if (options().onchips && (update.docChanged || update.transactions.some((tr) => tr.effects.some((e) => e.is(addChip))))) {
        options().onchips!(chipsOf(update.state));
      }
    }),
    look,
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
  initial.onview?.(view);
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
