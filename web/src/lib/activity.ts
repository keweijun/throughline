/**
 * Study activity (Settings → Activity): the host sends when things happened in each course; days and study time are
 * worked out here, in the learner's own time zone.
 */

export type ActivityKind = 'step' | 'answer' | 'question' | 'note' | 'drill';
export type ActivityView = {
  kinds: ActivityKind[];
  courses: { name: string; title: string; archived: boolean; events: [number, number][] }[];
};
export type Counts = Record<ActivityKind, number>;
export type CourseDay = { name: string; title: string; seconds: number; counts: Counts };
export type Day = { key: string; date: Date; seconds: number; courses: CourseDay[] };
export type CourseSpan = { name: string; title: string; archived: boolean; last: number; seconds: number };

/** Actions closer together than this are one sitting. */
export const GAP = 20 * 60;
/** A sitting lasts from its first action to its last, plus this for reading or answering that last one. */
export const CREDIT = 3 * 60;
/** How far back the calendar goes, in weeks. */
export const WEEKS = 26;

const KINDS: ActivityKind[] = ['step', 'answer', 'question', 'note', 'drill'];

const pad = (n: number) => String(n).padStart(2, '0');
export const dayKey = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/** Estimated seconds of study in a day's sorted action times. */
export function studied(times: number[]) {
  let total = 0;
  let start: number | null = null;
  let last = 0;
  for (const time of times) {
    if (start === null || time - last > GAP) {
      if (start !== null) total += last - start + CREDIT;
      start = time;
    }
    last = time;
  }
  return start === null ? 0 : total + last - start + CREDIT;
}

/** The Monday that starts the week of `date`, at midnight. */
export function weekStart(date: Date) {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

/** The first day the calendar shows: the Monday `WEEKS - 1` weeks before this week's. */
export function firstDay(today: Date) {
  const first = weekStart(today);
  first.setDate(first.getDate() - 7 * (WEEKS - 1));
  return first;
}

/** Days with activity, by `dayKey`, and each course's last activity and study time since `from`. */
export function summarize(view: ActivityView, from: Date) {
  const days = new Map<string, Day>();
  const times = new Map<string, number[]>(); // every course's times in a day, for the day's own estimate
  const courses: CourseSpan[] = [];
  const since = from.getTime() / 1000;
  for (const course of view.courses) {
    if (!course.events.length) continue;
    const perDay = new Map<string, { times: number[]; counts: Counts }>();
    for (const [time, kind] of course.events) {
      const key = dayKey(new Date(time * 1000));
      let entry = perDay.get(key);
      if (!entry) perDay.set(key, (entry = { times: [], counts: { step: 0, answer: 0, question: 0, note: 0, drill: 0 } }));
      entry.times.push(time);
      entry.counts[view.kinds[kind] ?? KINDS[kind]]++;
    }
    let seconds = 0;
    for (const [key, entry] of perDay) {
      const spent = studied(entry.times);
      if (entry.times[0] >= since) seconds += spent;
      const [y, m, d] = key.split('-').map(Number);
      let day = days.get(key);
      if (!day) days.set(key, (day = { key, date: new Date(y, m - 1, d), seconds: 0, courses: [] }));
      day.courses.push({ name: course.name, title: course.title, seconds: spent, counts: entry.counts });
      times.set(key, [...(times.get(key) ?? []), ...entry.times]);
    }
    courses.push({ name: course.name, title: course.title, archived: course.archived, last: course.events[course.events.length - 1][0], seconds });
  }
  for (const [key, day] of days) {
    day.seconds = studied((times.get(key) ?? []).sort((a, b) => a - b));
    day.courses.sort((a, b) => b.seconds - a.seconds);
  }
  courses.sort((a, b) => b.last - a.last);
  return { days, courses };
}

/** How dark a day's square is, from 0 (nothing) to 4, by fixed amounts of time so a square means the same every week. */
export function level(seconds: number) {
  if (!seconds) return 0;
  const minutes = seconds / 60;
  return minutes < 15 ? 1 : minutes < 45 ? 2 : minutes < 90 ? 3 : 4;
}
