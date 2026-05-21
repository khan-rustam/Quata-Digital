const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type ApiOptions = RequestInit & {
  token?: string;
  /** Override default fetch cache. Pass e.g. `force-cache` or
   *  `{ next: { revalidate: 60 } }` for RSC reads that can be cached. */
  cache?: RequestCache;
  /** Skip the global 401 handler — useful for the login form itself,
   *  where a 401 means "wrong credentials," not "session expired." */
  skipAuthRedirect?: boolean;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

/**
 * Hook for client code to react to a 401 (e.g. clear auth state, redirect
 * to /admin/login). Set once at app boot by the auth provider; defaults
 * to a no-op so server components don't crash trying to call it.
 */
let onUnauthorized: ((detail: unknown) => void) | null = null;
export function setUnauthorizedHandler(fn: ((detail: unknown) => void) | null) {
  onUnauthorized = fn;
}

export async function api<T = unknown>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const { token, headers, cache, skipAuthRedirect, ...rest } = options;
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    // Default to no-store so server components never silently cache a
    // user-specific response. Callers can opt back in (revalidate: 60)
    // for genuinely cacheable reads.
    cache: cache ?? "no-store",
  });

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = await res.json();
    } catch {
      /* response body was not JSON — fine */
    }
    const detailText =
      typeof detail === "string"
        ? detail
        : (detail as { detail?: string })?.detail ?? JSON.stringify(detail);

    // Central 401 handling: clear local auth state + bounce to login.
    // Skip when the caller is the login form itself (where 401 just
    // means "wrong password" and the page already handles it).
    if (res.status === 401 && !skipAuthRedirect && onUnauthorized) {
      try {
        onUnauthorized(detail);
      } catch {
        /* never propagate handler failures into the caller */
      }
    }

    throw new ApiError(res.status, detail, `API ${res.status}: ${detailText}`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiUrl = API_URL;
