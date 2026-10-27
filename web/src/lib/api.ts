export class ApiError extends Error {
  constructor(message: string, readonly code?: string, readonly status?: number) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    const file = body instanceof Blob;
    response = await fetch(path, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': file ? body.type : 'application/json' },
      body: body === undefined ? undefined : file ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError('The learning host is not reachable. Check that it is still running in your terminal.');
  }
  const data = await response.json().catch(() => ({}));
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
