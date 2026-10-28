// The "plot" add-on (ADR 0013): graphs of functions of x from a small `key: value` spec. Expressions are parsed here,
// never evaluated as JavaScript, so a lesson cannot run code through a plot.

type Fn = (x: number) => number;

const FUNCTIONS: Record<string, (v: number) => number> = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, exp: Math.exp, ln: Math.log, log10: Math.log10,
  sqrt: Math.sqrt, abs: Math.abs, floor: Math.floor, ceil: Math.ceil, sign: Math.sign,
};
const CONSTANTS: Record<string, number> = { pi: Math.PI, e: Math.E };
const MAX_FUNCTIONS = 6;
const MAX_POINTS = 20;

/** Compiles an expression in x; throws an Error saying what is wrong. */
export function compile(expression: string): Fn {
  const tokens = expression.match(/\d*\.?\d+(?:e[+-]?\d+)?|[a-z_][a-z0-9_]*|\S/gi) ?? [];
  let at = 0;
  const peek = () => tokens[at];
  const take = (want?: string) => {
    const token = tokens[at++];
    if (want !== undefined && token !== want) throw new Error(token === undefined ? `expected "${want}"` : `expected "${want}" before "${token}"`);
    return token;
  };
  function sum(): Fn {
    let left = product();
    while (peek() === '+' || peek() === '-') {
      const op = take(), a = left, b = product();
      left = op === '+' ? (x) => a(x) + b(x) : (x) => a(x) - b(x);
    }
    return left;
  }
  function product(): Fn {
    let left = unary();
    while (peek() === '*' || peek() === '/') {
      const op = take(), a = left, b = unary();
      left = op === '*' ? (x) => a(x) * b(x) : (x) => a(x) / b(x);
    }
    return left;
  }
  function unary(): Fn {
    if (peek() === '-') {
      take();
      const a = unary();
      return (x) => -a(x);
    }
    if (peek() === '+') {
      take();
      return unary();
    }
    return power();
  }
  function power(): Fn {
    const base = atom();
    if (peek() !== '^') return base;
    take();
    const exponent = unary();
    return (x) => Math.pow(base(x), exponent(x));
  }
  function atom(): Fn {
    const token = take();
    if (token === undefined) throw new Error('the expression ends early');
    if (token === '(') {
      const inner = sum();
      take(')');
      return inner;
    }
    if (/^\d|^\./.test(token)) {
      const value = Number(token);
      return () => value;
    }
    const name = token.toLowerCase();
    if (name === 'x') return (x) => x;
    if (name in CONSTANTS) return () => CONSTANTS[name];
    if (name in FUNCTIONS) {
      take('(');
      const argument = sum();
      take(')');
      const f = FUNCTIONS[name];
      return (x) => f(argument(x));
    }
    throw new Error(`unknown "${token}"`);
  }
  const result = sum();
  if (at < tokens.length) throw new Error(`unexpected "${tokens[at]}"`);
  return result;
}

type Spec = { functions: { text: string; f: Fn }[]; x: [number, number]; y?: [number, number]; points: { x: number; y: number; label: string }[] };

function constant(text: string) {
  const value = compile(text)(NaN);
  if (!Number.isFinite(value)) throw new Error(`"${text}" is not a number`);
  return value;
}

function range(text: string): [number, number] {
  const parts = text.split(',');
  if (parts.length !== 2) throw new Error(`a range is two numbers, as in "-3, 3"`);
  const [low, high] = parts.map(constant);
  if (!(low < high)) throw new Error(`a range must go from low to high`);
  return [low, high];
}

export function parse(source: string): Spec {
  const spec: Spec = { functions: [], x: [-5, 5], points: [] };
  for (const raw of source.split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const colon = line.indexOf(':');
    if (colon < 0) throw new Error(`"${line}" needs a key, as in "f: x^2"`);
    const key = line.slice(0, colon).trim().toLowerCase();
    const value = line.slice(colon + 1).trim();
    if (key === 'f') {
      spec.functions.push({ text: value, f: compile(value) });
    } else if (key === 'x') spec.x = range(value);
    else if (key === 'y') spec.y = range(value);
    else if (key === 'point') {
      const [x, y, ...label] = value.split(',');
      if (y === undefined) throw new Error(`a point is "x, y" with an optional label`);
      spec.points.push({ x: constant(x), y: constant(y), label: label.join(',').trim() });
    } else throw new Error(`unknown key "${key}"`);
  }
  if (!spec.functions.length) throw new Error('give at least one "f:" line');
  if (spec.functions.length > MAX_FUNCTIONS || spec.points.length > MAX_POINTS) throw new Error('too many functions or points');
  return spec;
}

/** A step of 1, 2 or 5 times a power of ten giving about `count` intervals. */
function step(span: number, count = 6) {
  const raw = span / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw)!;
}

function ticks([low, high]: [number, number]) {
  const size = step(high - low);
  const values = [];
  for (let v = Math.ceil(low / size) * size; v <= high + size * 1e-9; v += size) values.push(Math.abs(v) < size * 1e-9 ? 0 : v);
  return values;
}

const label = (v: number) => String(Number(v.toPrecision(4)));
const escape = (text: string) => text.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

function autoRange(samples: number[][]): [number, number] {
  const values = samples.flat().filter(Number.isFinite).sort((a, b) => a - b);
  if (!values.length) return [-1, 1];
  // Ignore the tails so an asymptote does not flatten the rest of the graph.
  const cut = values.length > 50 ? Math.floor(values.length * 0.03) : 0;
  let low = values[cut], high = values[values.length - 1 - cut];
  if (high - low < 1e-9) [low, high] = [low - 1, high + 1];
  const pad = (high - low) * 0.08;
  return [low - pad, high + pad];
}

const WIDTH = 560, HEIGHT = 340, LEFT = 44, RIGHT = 14, TOP = 14, BOTTOM = 30, SAMPLES = 600;

/** Draws a plot spec as SVG markup; throws an Error when the spec is invalid. */
export function drawPlot(source: string): string {
  const spec = parse(source);
  const [x0, x1] = spec.x;
  const xs = Array.from({ length: SAMPLES + 1 }, (_, i) => x0 + ((x1 - x0) * i) / SAMPLES);
  const samples = spec.functions.map(({ f }) => xs.map((x) => f(x)));
  const [y0, y1] = spec.y ?? autoRange(samples);
  const px = (x: number) => LEFT + ((x - x0) / (x1 - x0)) * (WIDTH - LEFT - RIGHT);
  const py = (y: number) => TOP + ((y1 - y) / (y1 - y0)) * (HEIGHT - TOP - BOTTOM);
  const inside = (y: number) => y >= y0 && y <= y1;
  const parts: string[] = [];
  for (const x of ticks([x0, x1])) {
    parts.push(`<line class="grid" x1="${px(x)}" x2="${px(x)}" y1="${TOP}" y2="${HEIGHT - BOTTOM}"/>`,
      `<text class="tick" x="${px(x)}" y="${HEIGHT - BOTTOM + 16}" text-anchor="middle">${label(x)}</text>`);
  }
  for (const y of ticks([y0, y1])) {
    parts.push(`<line class="grid" x1="${LEFT}" x2="${WIDTH - RIGHT}" y1="${py(y)}" y2="${py(y)}"/>`,
      `<text class="tick" x="${LEFT - 6}" y="${py(y) + 4}" text-anchor="end">${label(y)}</text>`);
  }
  if (x0 <= 0 && x1 >= 0) parts.push(`<line class="axis" x1="${px(0)}" x2="${px(0)}" y1="${TOP}" y2="${HEIGHT - BOTTOM}"/>`);
  if (inside(0)) parts.push(`<line class="axis" x1="${LEFT}" x2="${WIDTH - RIGHT}" y1="${py(0)}" y2="${py(0)}"/>`);
  const span = y1 - y0;
  samples.forEach((ys, index) => {
    let path = '';
    let drawing = false;
    ys.forEach((y, i) => {
      const previous = ys[i - 1];
      // Break at undefined values, and at a jump across the view that is an asymptote rather than a steep curve.
      const broken = !Number.isFinite(y) || (i > 0 && Number.isFinite(previous) && Math.abs(y - previous) > span * 2 && (!inside(y) || !inside(previous)));
      if (broken) {
        drawing = false;
        if (!Number.isFinite(y)) return;
      }
      const clamped = Math.min(Math.max(y, y0 - span), y1 + span);
      path += `${drawing ? 'L' : 'M'}${px(xs[i]).toFixed(1)} ${py(clamped).toFixed(1)}`;
      drawing = true;
    });
    parts.push(`<path class="curve series-${index}" clip-path="url(#plot-area)" d="${path}"/>`);
  });
  for (const point of spec.points) {
    if (point.x < x0 || point.x > x1 || !inside(point.y)) continue;
    parts.push(`<circle class="point" cx="${px(point.x)}" cy="${py(point.y)}" r="4"/>`);
    if (point.label) parts.push(`<text class="point-label" x="${px(point.x) + 7}" y="${py(point.y) - 7}">${escape(point.label)}</text>`);
  }
  const legend = spec.functions.map((f, index) => `<span class="key series-${index}">${escape(f.text)}</span>`).join('');
  const name = spec.functions.map((f) => f.text).join('; ');
  return `<svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Graph of ${escape(name)}"><defs><clipPath id="plot-area"><rect x="${LEFT}" y="${TOP}" width="${WIDTH - LEFT - RIGHT}" height="${HEIGHT - TOP - BOTTOM}"/></clipPath></defs>${parts.join('')}</svg>`
    + (spec.functions.length > 1 ? `<div class="legend">${legend}</div>` : '');
}
