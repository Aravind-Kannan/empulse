/**
 * Centralized API client with auth + tenant header injection.
 */

import { reportToastError } from "./toast-bus";

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
  /** When true, failed responses do not emit a global error toast. */
  skipErrorToast?: boolean;
  /** When true, omit Authorization / X-Tenant-ID (public probes). */
  skipAuth?: boolean;
};

async function parseResponseError(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const body = (await response.json()) as {
      detail?: string | Array<{ msg?: string; loc?: string[] }>;
      message?: string;
    };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail
        .map((item) => item.msg ?? JSON.stringify(item))
        .join("; ");
    }
    if (typeof body.message === "string" && body.message.trim()) {
      return body.message;
    }
  } catch {
    // Response body may not be JSON.
  }
  return `${fallback} (${response.status})`;
}

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
  const {
    timeoutMs = 20_000,
    signal: externalSignal,
    skipErrorToast = false,
    skipAuth = false,
    ...rest
  } = init ?? {};
  const headers = new Headers(rest.headers);

  if (!skipAuth) {
    const token = getAccessToken();
    const tenantId = getActiveTenantId();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (tenantId) {
      headers.set("X-Tenant-ID", tenantId);
    }
  }

  const runFetch = async (): Promise<Response> => {
    try {
      let response: Response;

      if (typeof window === "undefined" || externalSignal || timeoutMs === 0) {
        response = await fetch(url, {
          credentials: "include",
          ...rest,
          headers,
          signal: externalSignal,
        });
      } else {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => {
          controller.abort(
            new DOMException(
              `Request timed out after ${timeoutMs}ms`,
              "TimeoutError",
            ),
          );
        }, timeoutMs);

        try {
          response = await fetch(url, {
            credentials: "include",
            ...rest,
            headers,
            signal: controller.signal,
          });
        } finally {
          window.clearTimeout(timeoutId);
        }
      }

      if (!response.ok) {
        const message = await parseResponseError(
          response.clone(),
          "Request failed",
        );
        const suppressToast = skipErrorToast || response.status === 401;
        reportToastError(message, suppressToast);
      }

      return response;
    } catch (error) {
      reportToastError(formatFetchError(error), skipErrorToast);
      throw error;
    }
  };

  return runFetch();
}
