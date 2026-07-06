import { API_BASE, apiFetch, isFetchAbortError } from "./api-client";
import { isBackendWarmupActive } from "./backend-warmup-state";

export const AUTH_UNAVAILABLE_DIALOG_TITLE = "We're almost ready";

export class ServiceUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ServiceUnavailableError";
  }
}

/** API error with HTTP status — keeps 401 credential failures separate from warmup UX. */
export class HttpResponseError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "HttpResponseError";
    this.status = status;
  }
}

const GATEWAY_STATUSES = new Set([502, 503, 504]);

export function isGatewayStatus(status: number): boolean {
  return GATEWAY_STATUSES.has(status);
}

export function isUnreachableError(error: unknown): boolean {
  if (isFetchAbortError(error)) return true;
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    return true;
  }
  const message = errorMessage(error).toLowerCase();
  if (message.includes("failed to fetch")) return true;
  if (message.includes("timed out")) return true;
  if (message.includes("networkerror")) return true;
  return false;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "";
}

function hasTimeoutName(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const name = (error as { name?: string }).name;
  return name === "TimeoutError" || name === "AbortError";
}

export function isAuthServiceUnavailable(error: unknown): boolean {
  if (error instanceof HttpResponseError) {
    return isGatewayStatus(error.status);
  }
  if (error instanceof ServiceUnavailableError) return true;
  if (isUnreachableError(error)) return true;
  if (hasTimeoutName(error)) return true;
  const message = errorMessage(error).toLowerCase();
  if (/\b(502|503|504)\b/.test(message)) return true;
  if (message.includes("cannot reach the api server")) return true;
  if (message.includes("timed out")) return true;
  if (message.includes("failed to fetch")) return true;
  return false;
}

export function getAuthUnavailableMessage(
  warming = isBackendWarmupActive(),
): string {
  if (warming) {
    return "We're still starting up — sorry for the wait. On free hosting the first visit can take up to a minute. Please try again shortly.";
  }
  return "Sorry — we couldn't reach the server just now. It may still be waking up. Please wait a moment and try again.";
}

const PUBLIC_PROBE_INIT = {
  skipErrorToast: true,
  skipAuth: true,
  credentials: "omit" as const,
  cache: "no-store" as const,
};

export async function probeBackendReachable(
  timeoutMs = 10_000,
): Promise<boolean> {
  try {
    const response = await apiFetch(`${API_BASE}/`, {
      ...PUBLIC_PROBE_INIT,
      timeoutMs,
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function probeGoogleOAuthReady(
  timeoutMs = 10_000,
): Promise<"ready" | "unreachable" | "not_configured"> {
  try {
    const response = await apiFetch(`${API_BASE}/api/auth/providers`, {
      timeoutMs,
      skipErrorToast: true,
    });
    if (!response.ok) {
      return isGatewayStatus(response.status) ? "unreachable" : "not_configured";
    }
    const data = (await response.json()) as { google?: boolean };
    return data.google ? "ready" : "not_configured";
  } catch {
    return "unreachable";
  }
}

export async function throwIfAuthUnavailable(
  response: Response,
  fallback: string,
): Promise<void> {
  if (response.ok) return;
  if (isGatewayStatus(response.status)) {
    throw new ServiceUnavailableError(getAuthUnavailableMessage());
  }
  const body = await response.json().catch(() => null);
  const detail =
    typeof body?.detail === "string" ? body.detail : `${fallback} (${response.status})`;
  throw new HttpResponseError(detail, response.status);
}
