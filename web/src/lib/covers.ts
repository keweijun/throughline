/**
 * The patterns behind a course's name on its cover (ADR 0027). Codex chooses a pattern by name (`cover.save`); each is
 * drawn here from thin lines, gathered to the right of a 400 by 120 field so the name has clear paper on the left, and
 * varied by the course's folder name so two courses with one pattern still differ. A pattern this version does not
 * know is drawn as contours.
 */

/** One piece of a pattern: a path, how strongly it is drawn, and whether it is a filled dot or a heavier stroke. */
export type Mark = { d: string; tone: 'faint' | 'line' | 'marked'; dot?: boolean; wide?: boolean };

export const WIDTH = 400;
export const HEIGHT = 120;

const TAU = Math.PI * 2;
type Random = () => number;
type Point = [number, number];

function seeded(seed: string): Random {
  let state = [...seed].reduce((sum, char) => (sum * 31 + char.codePointAt(0)!) % 2147483647, 7) || 7;
  return () => (state = (state * 16807) % 2147483647) / 2147483647;
}

const n = (value: number) => value.toFixed(1);
const path = (points: Point[], close = false) => points.map(([x, y], i) => `${i ? 'L' : 'M'}${n(x)} ${n(y)}`).join('') + (close ? 'Z' : '');
const disc = (x: number, y: number, r: number) => `M${n(x - r)} ${n(y)}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;
/** A bell-shaped random number around zero, from three uniform ones. */
const bell = (random: Random) => (random() + random() + random() - 1.5) * 1.2;

// Which sides of a cell a level crosses, by which of its corners (top left, top right, bottom right, bottom left) are above it.
const [TOP, RIGHT, BOTTOM, LEFT] = [0, 1, 2, 3];
const CROSSINGS: Record<number, number[][]> = {
  1: [[LEFT, BOTTOM]], 2: [[BOTTOM, RIGHT]], 3: [[LEFT, RIGHT]], 4: [[TOP, RIGHT]], 5: [[TOP, RIGHT], [LEFT, BOTTOM]], 6: [[TOP, BOTTOM]], 7: [[TOP, LEFT]],
  8: [[TOP, LEFT]], 9: [[TOP, BOTTOM]], 10: [[TOP, LEFT], [BOTTOM, RIGHT]], 11: [[TOP, RIGHT]], 12: [[LEFT, RIGHT]], 13: [[BOTTOM, RIGHT]], 14: [[LEFT, BOTTOM]],
};

type Hill = { x: number; y: number; wide: number; tall: number; height: number };

/** The level curves of a few soft hills over a field, each level one path of short strokes (marching squares). */
function levels(hills: Hill[], width: number, height: number, step: number, count: number, slope: number, lean: number): string[] {
  const field = (x: number, y: number) =>
    hills.reduce((sum, h) => {
      const u = (x - h.x + lean * (y - h.y)) / h.wide;
      const v = (y - h.y) / h.tall;
      return sum + h.height * Math.exp(-u * u - v * v);
    }, 0) + x * slope;
  const edge = 2 * step;
  const columns = Math.ceil((width + 2 * edge) / step);
  const rows = Math.ceil((height + 2 * edge) / step);
  const values = Array.from({ length: rows + 1 }, (_, j) => Array.from({ length: columns + 1 }, (_, i) => field(i * step - edge, j * step - edge)));
  return Array.from({ length: count }, (_, k) => {
    const level = 0.07 + (k * 0.95) / (count - 1 || 1);
    let d = '';
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < columns; i++) {
        const [a, b, c, e] = [values[j][i], values[j][i + 1], values[j + 1][i + 1], values[j + 1][i]];
        const crossings = CROSSINGS[(a > level ? 8 : 0) | (b > level ? 4 : 0) | (c > level ? 2 : 0) | (e > level ? 1 : 0)];
        if (!crossings) continue;
        const [x, y] = [i * step - edge, j * step - edge];
        const at = (from: number, to: number) => ((level - from) / (to - from)) * step;
        const sides: Point[] = [[x + at(a, b), y], [x + step, y + at(b, c)], [x + at(e, c), y + step], [x, y + at(a, e)]];
        for (const [one, other] of crossings) d += `M${n(sides[one][0])} ${n(sides[one][1])}L${n(sides[other][0])} ${n(sides[other][1])}`;
      }
    }
    return d;
  });
}

/** Level curves of a few soft hills, as on a contour map. */
function contours(random: Random): Mark[] {
  const hills = [
    { x: 290 + random() * 70, y: 30 + random() * 60, wide: 62 + random() * 34, tall: 30 + random() * 16, height: 1 },
    { x: 190 + random() * 70, y: 15 + random() * 90, wide: 46 + random() * 30, tall: 24 + random() * 14, height: 0.5 + random() * 0.3 },
    { x: 350 + random() * 60, y: random() < 0.5 ? 10 + random() * 20 : 90 + random() * 20, wide: 40 + random() * 24, tall: 22 + random() * 12, height: 0.35 + random() * 0.3 },
  ];
  const lean = (random() - 0.5) * 0.5;
  const first = 3 + Math.floor(random() * 2);
  return levels(hills, WIDTH, HEIGHT, 6, 10, 0.00045, lean)
    .map((d, k) => ({ d, tone: k === first || k === first + 1 ? 'marked' : k < 2 ? 'faint' : 'line' }) as Mark)
    .filter((mark) => mark.d);
}

export const BACKDROP = { width: 1200, height: 560 };

let backdropMarks: Mark[] | undefined;

/** A wide contour map for the page a first course begins on: hills to either side, so the lines pass around the middle. */
export function backdrop(): Mark[] {
  backdropMarks ??= levels(
    [
      { x: 170, y: 150, wide: 330, tall: 190, height: 1 },
      { x: 1040, y: 330, wide: 350, tall: 210, height: 0.95 },
      { x: 640, y: 640, wide: 300, tall: 150, height: 0.5 },
      { x: 700, y: -90, wide: 260, tall: 120, height: 0.45 },
    ],
    BACKDROP.width, BACKDROP.height, 8, 15, 0, 0.2,
  ).map((d, k) => ({ d, tone: k === 6 || k === 7 ? 'marked' : k < 3 ? 'faint' : 'line' }) as Mark);
  return backdropMarks;
}

/** Traces stacked like a ridgeline plot, each a little out of step with the one above. */
function waves(random: Random): Mark[] {
  const centre = 250 + random() * 80;
  const spread = 85 + random() * 30;
  const beats = 2.3 + random() * 1.1;
  const drift = (random() < 0.5 ? -1 : 1) * (0.28 + random() * 0.2);
  const [phase, second] = [random() * TAU, random() * TAU];
  const first = 3 + Math.floor(random() * 5);
  const count = 13;
  return Array.from({ length: count }, (_, i) => {
    const y0 = 4 + i * 9.4;
    const size = 9.5 * (0.4 + 0.6 * Math.sin((Math.PI * (i + 0.5)) / count));
    const points: Point[] = [];
    for (let x = -4; x <= WIDTH + 4; x += 3) {
      const swell = Math.exp(-(((x - centre - (i - count / 2) * 5) / spread) ** 2));
      const t = (TAU * beats * x) / WIDTH;
      points.push([x, y0 + size * swell * (Math.sin(t + i * drift + phase) + 0.35 * Math.sin(2.1 * t - i * drift * 1.7 + second))]);
    }
    return { d: path(points), tone: i === first || i === first + 1 ? 'marked' : i < 2 || i > count - 3 ? 'faint' : 'line' } as Mark;
  });
}

/** A honeycomb, each edge drawn once, with three cells that touch picked out like fused rings. */
function lattice(random: Random): Mark[] {
  const r = 15;
  const w = r * Math.sqrt(3);
  const lift = random() * r;
  const shift = random() * w;
  const x = (i: number) => i * (w / 2) - shift;
  const y = (i: number, k: number) => k * 1.5 * r - lift + ((i + k) % 2 === 0 ? -r / 4 : r / 4);
  const columns = Math.ceil(WIDTH / (w / 2)) + 4;
  const marks: Mark[] = [];
  for (let k = 0; k < 8; k++) {
    marks.push({ d: path(Array.from({ length: columns }, (_, i) => [x(i), y(i, k)] as Point)), tone: 'line' });
    let ties = '';
    for (let i = 0; i < columns; i++) if ((i + k) % 2 === 1) ties += `M${n(x(i))} ${n(y(i, k))}L${n(x(i))} ${n(y(i, k + 1))}`;
    marks.push({ d: ties, tone: 'line' });
  }
  const k0 = 2 + Math.floor(random() * 2);
  const i0 = 2 * Math.round((250 + random() * 80 + shift) / w) + (k0 % 2);
  for (const [i, k] of [[i0, k0], [i0 + 2, k0], [i0 + 1, k0 + 1]]) {
    marks.push({ d: path([[x(i), y(i, k)], [x(i + 1), y(i + 1, k)], [x(i + 1), y(i + 1, k + 1)], [x(i), y(i, k + 1)], [x(i - 1), y(i - 1, k + 1)], [x(i - 1), y(i - 1, k)]], true), tone: 'marked' });
  }
  return marks;
}

/** A square grid carried by a smooth map of the plane, so its lines bend but still cross at right angles. */
function grid(random: Random): Mark[] {
  const bend = 0.1 + random() * 0.04;  // small enough that the map never folds inside the field
  const [turn, twist, tilt] = [random() * TAU, random() * TAU, -0.5 + random() * 0.6];
  const [ar, ai, br, bi] = [bend * Math.cos(turn), bend * Math.sin(turn), 0.018 * Math.cos(twist), 0.018 * Math.sin(twist)];
  const centre = [285 + random() * 30, 55 + random() * 12];
  const map = (u: number, v: number): Point => {
    // z + a z^2 + b z^3
    const [u2, v2] = [u * u - v * v, 2 * u * v];
    const [u3, v3] = [u2 * u - v2 * v, u2 * v + v2 * u];
    const p = u + ar * u2 - ai * v2 + br * u3 - bi * v3;
    const q = v + ar * v2 + ai * u2 + br * v3 + bi * u3;
    return [centre[0] + 78 * (p * Math.cos(tilt) - q * Math.sin(tilt)), centre[1] + 78 * (p * Math.sin(tilt) + q * Math.cos(tilt))];
  };
  const marked = Math.floor(-3 + random() * 5);
  const marks: Mark[] = [];
  for (let i = -15; i <= 15; i++) {
    const at = i * 0.17;
    const along = Array.from({ length: 49 }, (_, j) => -2.6 + (j * 5.2) / 48);
    marks.push({ d: path(along.map((t) => map(at, t))), tone: i === marked || i === marked + 1 ? 'marked' : 'line' });
    marks.push({ d: path(along.map((t) => map(t, at))), tone: 'line' });
  }
  return marks;
}

/** Nested ellipses, each turned a little further than the one inside it, with a body on one of them. */
function orbits(random: Random): Mark[] {
  const [cx, cy] = [290 + random() * 40, 52 + random() * 16];
  const tilt = random() * Math.PI;
  const twist = (random() < 0.5 ? -1 : 1) * (0.05 + random() * 0.035);
  const flat = 0.42 + random() * 0.12;
  const marked = 5 + Math.floor(random() * 3);
  const where = random() * TAU;
  const on = (i: number, t: number): Point => {
    const [a, rx] = [tilt + i * twist, 16 + i * 11];
    const ry = rx * flat;
    return [cx + rx * Math.cos(t) * Math.cos(a) - ry * Math.sin(t) * Math.sin(a), cy + rx * Math.cos(t) * Math.sin(a) + ry * Math.sin(t) * Math.cos(a)];
  };
  const marks: Mark[] = Array.from({ length: 18 }, (_, i) => ({
    d: path(Array.from({ length: 96 }, (_, j) => on(i, (TAU * j) / 96)), true),
    tone: i === marked || i === marked + 1 ? 'marked' : i > 14 ? 'faint' : 'line',
  }));
  let body = on(marked + 1, where);
  for (let tries = 0; tries < 16 && (body[0] < 170 || body[0] > WIDTH - 14 || body[1] < 12 || body[1] > HEIGHT - 12); tries++) body = on(marked + 1, random() * TAU);
  marks.push({ d: disc(cx, cy, 2), tone: 'line', dot: true }, { d: disc(...body, 2.6), tone: 'marked', dot: true });
  return marks;
}

/** Field lines leaving one pole and gathering at another. */
function field(random: Random): Mark[] {
  const angle = (random() - 0.5) * 0.9;
  const half = 52 + random() * 14;
  const [mx, my] = [300 + random() * 26, 56 + random() * 10];
  const from: Point = [mx - half * Math.cos(angle), my - half * Math.sin(angle)];
  const to: Point = [mx + half * Math.cos(angle), my + half * Math.sin(angle)];
  const lines = 30;
  const traced: { points: Point[]; arrived: boolean }[] = [];
  for (let i = 0; i < lines; i++) {
    const start = angle + (TAU * (i + 0.5)) / lines;
    let [x, y] = [from[0] + 8 * Math.cos(start), from[1] + 8 * Math.sin(start)];
    const points: Point[] = [[x, y]];
    let arrived = false;
    for (let step = 0; step < 420 && !arrived; step++) {
      const pull = (pole: Point, sign: number) => {
        const [dx, dy] = [x - pole[0], y - pole[1]];
        const cube = (dx * dx + dy * dy) ** 1.5 + 1e-6;
        return [(sign * dx) / cube, (sign * dy) / cube];
      };
      const [out, back] = [pull(from, 1), pull(to, -1)];
      const [ex, ey] = [out[0] + back[0], out[1] + back[1]];
      const size = Math.hypot(ex, ey) || 1;
      x += (2.5 * ex) / size;
      y += (2.5 * ey) / size;
      points.push([x, y]);
      arrived = Math.hypot(x - to[0], y - to[1]) < 8;
      if (x < -120 || x > WIDTH + 120 || y < -160 || y > HEIGHT + 160) break;
    }
    traced.push({ points, arrived });
  }
  // The marked pair runs from pole to pole inside the field, where it can be followed.
  const inside = (line: { points: Point[]; arrived: boolean }) => line.arrived && line.points.every(([, y]) => y > 4 && y < HEIGHT - 4);
  const pairs = traced.map((_, i) => i).filter((i) => inside(traced[i]) && inside(traced[(i + 1) % lines]));
  const marked = pairs.length ? pairs[Math.floor(random() * pairs.length)] : -2;
  const marks: Mark[] = traced.map((line, i) => ({ d: path(line.points), tone: i === marked || i === (marked + 1) % lines ? 'marked' : 'line' }));
  marks.push({ d: disc(...from, 3), tone: 'marked', dot: true }, { d: disc(...to, 3), tone: 'faint', dot: true });
  return marks;
}

/** A tree that forks level by level from the right, some branches ending early, with one path from the root marked. */
function branches(random: Random): Mark[] {
  const across = (depth: number) => 388 - depth * 41;
  const marks: Mark[] = [];
  const dots: Mark[] = [];
  const grow = (depth: number, y: number, span: number, onPath: boolean) => {
    dots.push({ d: disc(across(depth), y, onPath ? 2.4 : depth > 3 ? 1.2 : 1.8), tone: onPath ? 'marked' : 'line', dot: true });
    if (depth === 5 || (depth > 1 && random() < 0.16)) return;
    const chosen = onPath && depth < 4 ? (random() < 0.5 ? 0 : 1) : -1;
    [-1, 1].forEach((side, index) => {
      const childY = y + side * (span / 2) * (0.86 + random() * 0.28);
      const [x0, x1] = [across(depth), across(depth + 1)];
      const marked = index === chosen;
      marks.push({ d: `M${n(x0)} ${n(y)}C${n(x0 - 24)} ${n(y)} ${n(x1 + 24)} ${n(childY)} ${n(x1)} ${n(childY)}`, tone: marked ? 'marked' : depth > 3 ? 'faint' : 'line' });
      grow(depth + 1, childY, span / 2, marked);
    });
  };
  grow(0, 54 + random() * 12, 60, true);
  // Marked branches are drawn last, over the others.
  return [...marks.filter((m) => m.tone !== 'marked'), ...marks.filter((m) => m.tone === 'marked'), ...dots];
}

/** A cloud of points around a trend, with the trend line through it. */
function scatter(random: Random): Mark[] {
  const rise = (random() < 0.75 ? -1 : 1) * (0.16 + random() * 0.14);
  const curve = (random() - 0.5) * 0.0009;
  const middle = 58 + random() * 8;
  const trend = (x: number) => middle + rise * (x - 285) + curve * (x - 285) ** 2;
  const marks: Mark[] = [];
  for (let i = 0; i < 120; i++) {
    const x = 175 + random() * 225;
    const y = trend(x) + bell(random) * (14 + (x - 175) * 0.035);
    if (y < 5 || y > HEIGHT - 5) continue;
    marks.push({ d: disc(x, y, random() < 0.18 ? 2.5 : 1.7), tone: random() < 0.35 ? 'faint' : 'line', dot: true });
  }
  const across = Array.from({ length: 40 }, (_, j) => 120 + (j * 290) / 39);
  for (const offset of [-26, 26]) marks.push({ d: path(across.map((x) => [x, trend(x) + offset * (1 + ((x - 285) / 260) ** 2)])), tone: 'faint' });
  marks.push({ d: path(across.map((x) => [x, trend(x)])), tone: 'marked' });
  return marks;
}

/** Lines of writing set in paragraphs, a passage of one marked as with a highlighter. */
function ruled(random: Random): Mark[] {
  const [left, right] = [150, 392];
  const marks: Mark[] = [];
  const rows = 10;
  const markedRow = 2 + Math.floor(random() * 5);
  let indent = true;
  for (let row = 0; row < rows; row++) {
    const y = 12 + row * 10.6;
    const last: boolean = !indent && random() < 0.22;  // a paragraph's short last line
    const end = last ? left + 60 + random() * 110 : right;
    let x = left + (indent ? 16 : 0);
    const words: Point[] = [];
    while (x < end - 10) {
      const length = Math.min(9 + random() * 30, end - x);
      words.push([x, x + length]);
      x += length + 6;
    }
    const start = row === markedRow ? Math.floor(random() * Math.max(1, words.length - 4)) : -1;
    words.forEach(([from, to], index) => {
      const marked = start >= 0 && index >= start && index < start + 3 + Math.floor(words.length / 4);
      marks.push({ d: `M${n(from)} ${n(y)}L${n(to)} ${n(y)}`, tone: marked ? 'marked' : 'line', wide: true });
    });
    indent = last;
  }
  return marks;
}

const PATTERNS: Record<string, (random: Random) => Mark[]> = { contours, waves, lattice, grid, orbits, field, branches, scatter, ruled };

const drawn = new Map<string, Mark[]>();

/** The marks of a pattern for one course; the same pattern and seed always give the same drawing. */
export function coverPattern(pattern: string | undefined | null, seed: string): Mark[] {
  const name = pattern && pattern in PATTERNS ? pattern : 'contours';
  const key = `${name}\n${seed}`;
  let marks = drawn.get(key);
  if (!marks) {
    marks = PATTERNS[name](seeded(seed));
    drawn.set(key, marks);
  }
  return marks;
}
