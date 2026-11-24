/**
 * Desktop notifications for Studio (Settings → Teacher → Studio). The browser grants the permission per site, so the
 * choice is kept in this browser too, like the theme.
 */
const KEY = 'notify';

function current(): NotificationPermission | 'unsupported' {
  return typeof Notification === 'undefined' ? 'unsupported' : Notification.permission;
}

function wanted() {
  try {
    return localStorage.getItem(KEY) === 'studio';
  } catch {
    return false;
  }
}

export const notifications = $state({ on: wanted() && current() === 'granted', permission: current() });

/** Reads the permission again: the learner may have changed it in the browser since. */
export function refreshNotifications() {
  notifications.permission = current();
  notifications.on = wanted() && notifications.permission === 'granted';
}

/** Turns notifications on, asking the browser first when it has not been asked, or off. */
export async function setNotifications(on: boolean) {
  if (on && current() === 'default') notifications.permission = await Notification.requestPermission();
  else notifications.permission = current();
  notifications.on = on && notifications.permission === 'granted';
  try {
    if (notifications.on) localStorage.setItem(KEY, 'studio');
    else localStorage.removeItem(KEY);
  } catch {
    // The choice still holds for this visit.
  }
}

/** Shows a notification while the learner is in another tab or app; Throughline on screen shows what happened itself. */
export function notify(title: string, body: string, tag: string, onClick: () => void) {
  if (!notifications.on || current() !== 'granted') return;
  if (document.visibilityState === 'visible' && document.hasFocus()) return;
  const note = new Notification(title, { body, tag, icon: '/favicon.svg' });
  note.onclick = () => {
    window.focus();
    onClick();
    note.close();
  };
}
