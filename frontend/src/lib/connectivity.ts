import {
  isFetchAbortError,
} from "./api-client";
import { isBackendWarmupActive } from "./backend-warmup-state";

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
  return false;
}

export function isAuthServiceUnavailable(error: unknown): boolean {
  if (error instanceof HttpResponseError) {
    return isGatewayStatus(error.status);
  }
  if (error instanceof ServiceUnavailableError) return true;
  if (isUnreachableError(error)) return true;
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    if (/\b(502|503|504)\b/.test(message)) return true;
    if (message.includes("cannot reach the api server")) return true;
    if (message.includes("timed out")) return true;
  }
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
