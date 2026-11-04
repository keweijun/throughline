/**
 * A modal closes when the learner clicks its backdrop, as Escape closes it. A press that starts inside the dialog and
 * ends outside it, such as selecting text, does not count, nor does a click on something above the dialog, such as the
 * error toast. Closing goes through `close()`, so the dialog's own `close` handler runs as it does for Escape.
 */
export function lightDismiss(dialog: HTMLDialogElement) {
  let pressed = false;
  // A click on the backdrop targets the dialog itself, outside its box.
  const outside = (event: MouseEvent) => {
    if (event.target !== dialog) return false;
    const box = dialog.getBoundingClientRect();
    return event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom;
  };
  const down = (event: PointerEvent) => (pressed = outside(event));
  const click = (event: MouseEvent) => {
    if (pressed && outside(event)) dialog.close();
    pressed = false;
  };
  dialog.addEventListener('pointerdown', down);
  dialog.addEventListener('click', click);
  return {
    destroy() {
      dialog.removeEventListener('pointerdown', down);
      dialog.removeEventListener('click', click);
    },
  };
}
