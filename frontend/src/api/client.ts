/**
 * The single place where the browser talks HTTP to Django.
 *
 * Every feature module (auth, customers, invoices, ...) calls `apiRequest`, so
 * cookies, CSRF, JSON parsing and error normalisation are implemented exactly once.
 */

const API_BASE = "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/** Mirrors the backend error envelope: {"error": {code, message, details}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field-level validation messages, e.g. {email: ["Enter a valid email address."]}. */
  get fieldErrors(): Record<string, string[]> {
    if (this.code !== "validation_error") return {};
    return this.details as Record<string, string[]>;
  }
}

/** Standard paginated list response produced by apps.core.pagination.StandardPagination. */
export interface Paginated<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  return url.pathname + url.search;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!SAFE_METHODS.has(method)) {
    // Django's CsrfViewMiddleware compares this header with the csrftoken cookie.
    const token = readCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      credentials: "same-origin", // send the HttpOnly session cookie
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Cannot reach the server. Check your connection.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const envelope = (payload as { error?: { code: string; message: string; details?: Record<string, unknown> } })
      ?.error;
    if (envelope) {
      throw new ApiError(response.status, envelope.code, envelope.message, envelope.details ?? {});
    }
    throw new ApiError(response.status, "http_error", `Request failed with status ${response.status}.`, {
      body: payload,
    });
  }

  return payload as T;
}
