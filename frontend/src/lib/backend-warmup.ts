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

async function pingBackend(): Promise<boolean> {
  try {
    const response = await apiFetch(`${API_BASE}/`, {
      timeoutMs: WARMUP_TIMEOUT_MS,
      skipErrorToast: true,
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function pingDatabase(): Promise<boolean> {
  try {
    const response = await apiFetch(`${API_BASE}/health/db`, {
      timeoutMs: WARMUP_TIMEOUT_MS,
      skipErrorToast: true,
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function attemptWarmup(): Promise<boolean> {
  const [backendOk, dbOk] = await Promise.all([
    pingBackend(),
    pingDatabase(),
  ]);
  return backendOk && dbOk;
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
