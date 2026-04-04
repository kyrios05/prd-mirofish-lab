/**
 * api/client.ts — Base HTTP client for the PRD MiroFish Lab API.
 *
 * Design decisions
 * ----------------
 * - Native fetch only (no axios/ky) to keep the dependency footprint minimal.
 * - BASE_URL is resolved from VITE_API_URL env var; falls back to localhost:8000
 *   for local development.
 * - All requests set Content-Type: application/json by default.
 * - Non-2xx responses throw ApiError with status + detail from FastAPI body.
 * - T07: client configuration only — no state management, no caching.
 *
 * Scope guard
 * -----------
 * - Real MiroFish HTTP calls: T10
 * - State management (zustand etc.): T08
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Base URL for all API calls.
 * Set VITE_API_URL in .env (or .env.local) to override.
 * Default: http://localhost:8000
 */
export const BASE_URL: string =
  (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000';

// ---------------------------------------------------------------------------
// ApiError
// ---------------------------------------------------------------------------

/**
 * Thrown whenever the API responds with a non-2xx status code.
 *
 * @example
 * try {
 *   await chatApi.sendMessage(req);
 * } catch (err) {
 *   if (err instanceof ApiError && err.status === 404) {
 *     // session not found
 *   }
 * }
 */
export class ApiError extends Error {
  /** HTTP status code (e.g. 404, 422, 500). */
  readonly status: number;
  /** Raw response body from FastAPI (may be { detail: ... }). */
  readonly detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

interface RequestOptions {
  method: HttpMethod;
  path: string;
  body?: unknown;
  /** Additional headers to merge. */
  headers?: Record<string, string>;
}

/**
 * Parse a FastAPI error response and extract a human-readable message.
 */
async function parseErrorResponse(res: Response): Promise<{ message: string; detail: unknown }> {
  let detail: unknown;
  try {
    detail = await res.json();
  } catch {
    detail = await res.text().catch(() => null);
  }

  let message = `HTTP ${res.status} ${res.statusText}`;
  if (detail && typeof detail === 'object' && 'detail' in detail) {
    const d = (detail as { detail: unknown }).detail;
    if (typeof d === 'string') {
      message = d;
    } else if (Array.isArray(d)) {
      // FastAPI validation error array
      message = d.map((e: unknown) => {
        if (e && typeof e === 'object' && 'msg' in e) {
          return String((e as { msg: unknown }).msg);
        }
        return String(e);
      }).join('; ');
    }
  }

  return { message, detail };
}

// ---------------------------------------------------------------------------
// Public request wrapper
// ---------------------------------------------------------------------------

/**
 * Generic fetch wrapper.  All API functions delegate to this.
 *
 * @param options.method  HTTP method
 * @param options.path    Path relative to BASE_URL (must start with '/')
 * @param options.body    Request body (will be JSON-serialised)
 * @returns Parsed JSON response cast to T
 * @throws ApiError on non-2xx responses
 * @throws TypeError on network failure (re-thrown as-is)
 */
export async function request<T>(options: RequestOptions): Promise<T> {
  const { method, path, body, headers: extraHeaders } = options;

  const url = `${BASE_URL}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...extraHeaders,
  };

  const init: RequestInit = {
    method,
    headers,
    // Only attach a body for methods that support it
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  };

  const res = await fetch(url, init);

  if (!res.ok) {
    const { message, detail } = await parseErrorResponse(res);
    throw new ApiError(res.status, message, detail);
  }

  // 204 No Content — return empty object cast to T
  if (res.status === 204) {
    return {} as T;
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Convenience wrappers (used by domain API modules)
// ---------------------------------------------------------------------------

export const get = <T>(path: string): Promise<T> =>
  request<T>({ method: 'GET', path });

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>({ method: 'POST', path, body });
