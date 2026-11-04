import { prefersReducedMotion } from 'svelte/motion';
import type { TransitionConfig } from 'svelte/transition';

/*
 * The app's motion tokens for Svelte transitions, the counterpart of the ones in app.css: a block that comes and goes
 * arrives with `--settle` and `--ease-out`, and leaves the way it came with `--leave` and `--ease-in`. Keep the two
 * in step. Reduced motion makes every transition instant.
 */
const SETTLE = 220;
const LEAVE = 150;

/** A CSS cubic-bezier timing function, so a transition eases exactly as the matching CSS token does. */
function bezier(x1: number, y1: number, x2: number, y2: number) {
  const at = (a: number, b: number, t: number) => 3 * a * t * (1 - t) ** 2 + 3 * b * t ** 2 * (1 - t) + t ** 3;
  return (x: number) => {
    if (x <= 0 || x >= 1) return x;
    let lo = 0;
    let hi = 1;
    let t = x;
    for (let i = 0; i < 24; i++) {
      if (at(x1, x2, t) < x) lo = t;
      else hi = t;
      t = (lo + hi) / 2;
    }
    return at(y1, y2, t);
  };
}

const easeOut = bezier(0.2, 0.7, 0.2, 1);
const easeIn = bezier(0.5, 0, 0.75, 0.2);

// Svelte calls a transition's returned function with the direction it plays in; its types do not say so.
type Direction = { direction?: 'in' | 'out' | 'both' };
type Motion = (options?: Direction) => TransitionConfig;

function timing({ direction }: Direction = {}) {
  if (prefersReducedMotion.current) return { duration: 0 };
  return direction !== 'out' ? { duration: SETTLE, easing: easeOut } : { duration: LEAVE, easing: easeIn };
}

/**
 * A popup or menu: fades and grows a little from the edge it is anchored to. `from` is where it comes from:
 * 'below' for one that opens upward over what it belongs to, 'above' for one that drops down.
 */
export function pop(_node: Element, { from = 'below' }: { from?: 'below' | 'above' } = {}): Motion {
  const offset = from === 'below' ? 4 : -4;
  return (options) => ({
    ...timing(options),
    css: (t, u) => `opacity: ${t}; scale: ${0.97 + 0.03 * t}; translate: 0 ${offset * u}px;`,
  });
}

/** A block that opens out of the flow and folds back into it, such as a chapter's sections in the route. */
export function fold(node: Element): Motion {
  const sides = ['padding-top', 'padding-bottom', 'margin-top', 'margin-bottom'];
  return (options) => {
    // Measured each time it plays, since what the block holds may have changed since it opened.
    const style = getComputedStyle(node);
    const height = parseFloat(style.height);
    const sizes = sides.map((side) => parseFloat(style.getPropertyValue(side)));
    return {
      ...timing(options),
      css: (t) =>
        `overflow: hidden; opacity: ${Math.min(t * 1.5, 1)}; height: ${t * height}px;` +
        sides.map((side, i) => `${side}: ${t * sizes[i]}px;`).join(''),
    };
  };
}
