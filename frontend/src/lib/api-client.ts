/**
 * Centralized API client with auth + tenant header injection.
 */

const TOKEN_STORAGE_KEY = "empulse_access_token";
const TENANT_STORAGE_KEY = "empulse_active_tenant_id";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let memoryAccessToken: string | null = null;
let memoryTenantId: string | null = null;

export function setAuthCredentials(token: string | null, tenantId: string | null) {
  memoryAccessToken = token;
  memoryTenantId = tenantId;
  if (typeof window === "undefined") return;
  if (token) {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
  if (tenantId) {
    sessionStorage.setItem(TENANT_STORAGE_KEY, tenantId);
  } else {
    sessionStorage.removeItem(TENANT_STORAGE_KEY);
  }
}

export function getAccessToken(): string | null {
  if (memoryAccessToken) return memoryAccessToken;
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function getActiveTenantId(): string | null {
  if (memoryTenantId) return memoryTenantId;
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TENANT_STORAGE_KEY);
}

export function clearAuthCredentials() {
  setAuthCredentials(null, null);
}

export type ApiFetchInit = RequestInit & {
  /** Client-side timeout in ms. Default 20s. Set 0 to disable. */
  timeoutMs?: number;
};

export function isFetchAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === "AbortError" || error.name === "TimeoutError";
  }
  return false;
}

export function formatFetchError(
  error: unknown,
  fallback = "Request failed",
): string {
  if (isFetchAbortError(error)) {
    return "API request timed out. Backend may be busy with a sync — wait and retry, or restart the server.";
  }
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    return "Cannot reach the API server. Ensure the backend is running on port 8000.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function apiFetch(url: string, init?: ApiFetchInit): Promise<Response> {
  const { timeoutMs = 20_000, signal: externalSignal, ...rest } = init ?? {};
  const headers = new Headers(rest.headers);
  const token = getAccessToken();
  const tenantId = getActiveTenantId();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (tenantId) {
    headers.set("X-Tenant-ID", tenantId);
  }

  if (typeof window === "undefined" || externalSignal || timeoutMs === 0) {
    return fetch(url, {
      credentials: "include",
      ...rest,
      headers,
      signal: externalSignal,
    });
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort(
      new DOMException(
        `Request timed out after ${timeoutMs}ms`,
        "TimeoutError",
      ),
    );
  }, timeoutMs);

  return fetch(url, {
    credentials: "include",
    ...rest,
    headers,
    signal: controller.signal,
  }).finally(() => {
    window.clearTimeout(timeoutId);
  });
}
