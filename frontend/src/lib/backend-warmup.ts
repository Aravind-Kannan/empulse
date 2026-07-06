import { API_BASE, apiFetch } from "./api-client";
import {
  isBackendWarmupActive,
  setBackendWarming,
} from "./backend-warmup-state";
import { isProductionApp } from "./env";

const WARMUP_TIMEOUT_MS = 30_000;
const RETRY_INTERVAL_MS = 15_000;

let started = false;
let retryTimer: ReturnType<typeof setInterval> | null = null;

function clearRetry() {
  if (retryTimer !== null) {
    clearInterval(retryTimer);
    retryTimer = null;
  }
}

function markReady() {
  setBackendWarming(false);
  clearRetry();
}

/** Call when a client probe confirms API + Postgres are reachable. */
export function notifyBackendServicesReady(): void {
  markReady();
}

async function pingBackend(timeoutMs = WARMUP_TIMEOUT_MS): Promise<boolean> {
  try {
    const response = await apiFetch(`${API_BASE}/`, {
      timeoutMs,
      skipErrorToast: true,
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function pingDatabase(timeoutMs = WARMUP_TIMEOUT_MS): Promise<boolean> {
  try {
    const response = await apiFetch(`${API_BASE}/health/db`, {
      timeoutMs,
      skipErrorToast: true,
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function attemptWarmup(timeoutMs = WARMUP_TIMEOUT_MS): Promise<boolean> {
  const status = await probeBackendServicesStatus(timeoutMs);
  return status.api && status.database;
}

export type BackendProbeStatus = {
  api: boolean;
  database: boolean;
};

/** Probe Render API first, then Postgres — only checks DB after API is up. */
export async function probeBackendServicesStatus(
  timeoutMs = WARMUP_TIMEOUT_MS,
): Promise<BackendProbeStatus> {
  const api = await pingBackend(timeoutMs);
  if (!api) {
    return { api: false, database: false };
  }
  const database = await pingDatabase(timeoutMs);
  return { api: true, database };
}

/** Quick readiness check for auth flows (short timeout). */
export async function pingBackendServices(
  timeoutMs = 2_500,
): Promise<boolean> {
  const status = await probeBackendServicesStatus(timeoutMs);
  return status.api && status.database;
}

/** Silently ping API + Postgres until both are reachable (production only). */
export function startBackendWarmup(): void {
  if (started) return;
  started = true;

  if (!isProductionApp) {
    markReady();
    return;
  }

  setBackendWarming(true);

  const attempt = async () => {
    if (await attemptWarmup()) {
      markReady();
    }
  };

  void attempt();

  retryTimer = setInterval(() => {
    if (!isBackendWarmupActive()) {
      clearRetry();
      return;
    }
    void attempt();
  }, RETRY_INTERVAL_MS);
}
