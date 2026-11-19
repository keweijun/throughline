export class ApiError extends Error {
  constructor(message: string, readonly code?: string, readonly status?: number) {
    super(message);
  }
}

/** Called when the host refuses a browser without its key (a tab opened some other way than the launcher). */
export const signIn = { refused: () => {} };

/**
 * The course this page loaded, named in every request so the host refuses one meant for it once another course is open
 * (`course_changed`); the page then reloads into the open course, as it does when told the course switched.
 */
export const course = {
  /** The course's key: its ID and its folder, so a copy of the course folder is another course. */
  key: null as string | null,
  changed: () => location.reload(),
};

/** A plain link to a course-scoped endpoint (a download or an image), which cannot send the header, names the course. */
export function courseUrl(path: string) {
  return course.key ? `${path}${path.includes('?') ? '&' : '?'}course=${encodeURIComponent(course.key)}` : path;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    const file = body instanceof Blob;
    const headers: Record<string, string> = course.key ? { 'X-Throughline-Course': course.key } : {};
    if (body !== undefined) headers['Content-Type'] = file ? body.type : 'application/json';
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : file ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('The learning host is not reachable. Check that it is still running in your terminal.');
  }
  const data = await response.json().catch(() => ({}));
  if (response.status === 401 && data.code === 'not_signed_in') signIn.refused();
  if (response.status === 409 && data.code === 'course_changed') {
    // Not an error to show: what the page asked for belongs to a course no longer open, and the page is about to go.
    course.changed();
    return new Promise<T>(() => {});
  }
  if (!response.ok) throw new ApiError(data.error ?? `Request failed (${response.status})`, data.code, response.status);
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  /** Sends a file as the raw request body, typed by the file. */
  upload: <T>(path: string, file: Blob) => request<T>('POST', path, file),
};

export const newId = () => crypto.randomUUID();
