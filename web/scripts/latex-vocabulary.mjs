// Builds src/lib/latex-vocabulary.json, the LaTeX commands and environments the composer suggests, from KaTeX itself:
// every name KaTeX's source defines, kept only when KaTeX renders it, with the number of arguments it needs. So the
// suggestions are exactly what the preview and the lessons can show. Run after upgrading KaTeX: npm run vocabulary
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const katex = require('katex');
const src = path.join(path.dirname(require.resolve('katex/package.json')), 'src');
const files = (dir) => readdirSync(dir).filter((f) => f.endsWith('.ts') || f.endsWith('.js')).map((f) => readFileSync(path.join(dir, f), 'utf8'));
const sources = [...files(src), ...files(path.join(src, 'functions')), ...files(path.join(src, 'environments'))].join('\n');

// Some environments, such as align, only exist in display math.
const renders = (tex, displayMode = false) => {
  try {
    katex.renderToString(tex, { throwOnError: true, strict: 'ignore', trust: false, displayMode });
    return true;
  } catch {
    return false;
  }
};

// Commands that render but are not written by hand: internal, plain-TeX primitives, or for page layout.
const skip = new Set(['relax', 'expandafter', 'noexpand', 'def', 'gdef', 'edef', 'xdef', 'let', 'futurelet', 'global', 'long',
  'newcommand', 'renewcommand', 'providecommand', 'char', 'TextOrMath', 'nonscript', 'hspace', 'kern', 'mkern', 'mskip', 'hskip',
  'htmlClass', 'htmlId', 'htmlStyle', 'htmlData', 'href', 'url', 'includegraphics', 'vcenter', 'mathchoice', 'begingroup', 'endgroup',
  'begin', 'end', 'verb', 'show', 'message', 'errmessage', 'typeout', 'showbox', 'cr', 'hline', 'hdashline', 'tag', 'notag', 'nonumber', 'label', 'ref', 'eqref', 'limits', 'nolimits']);

// \show and its kin print while they are tried; the console is not part of the vocabulary.
const log = console.log;
console.log = () => {};
const names = new Set([...sources.matchAll(/["']\\\\([A-Za-z]+)["']/g)].map((m) => m[1]));
const commands = [];
for (const name of [...names].sort()) {
  if (skip.has(name) || name.startsWith('KaTeX')) continue;
  // The fewest braced arguments it renders with is the number it needs.
  const arity = [0, 1, 2, 3].find((n) => renders(`\\${name}${'{x}'.repeat(n)}`));
  if (arity !== undefined) commands.push([name, arity]);
}

const environments = [...new Set([...sources.matchAll(/names:\s*\[([^\]]*)\]/g)].flatMap((m) => [...m[1].matchAll(/["']([A-Za-z*]+)["']/g)].map((n) => n[1])))]
  .filter((name) => renders(`\\begin{${name}}${name.startsWith('array') || name.startsWith('darray') || name.startsWith('subarray') ? '{c}' : name.startsWith('alignat') || name === 'alignedat' ? '{1}' : ''}x\\end{${name}}`, true))
  .sort();

const out = path.join(path.dirname(new URL(import.meta.url).pathname), '../src/lib/latex-vocabulary.json');
writeFileSync(out, JSON.stringify({ katex: katex.version, commands, environments }) + '\n');
console.log = log;
console.log(`${commands.length} commands, ${environments.length} environments from KaTeX ${katex.version}`);
