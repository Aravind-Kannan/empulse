"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { API_BASE, apiFetch } from "@/lib/api-client";
import { isProductionApp } from "@/lib/env";

const WARMUP_TIMEOUT_MS = 30_000;
const RETRY_INTERVAL_MS = 15_000;

type WarmupState = "idle" | "checking" | "ok" | "unavailable";

interface PostgresWarmupBannerProps {
  onVisibleChange?: (visible: boolean) => void;
}

export function PostgresWarmupBanner({
  onVisibleChange,
}: PostgresWarmupBannerProps) {
  const [state, setState] = useState<WarmupState>("idle");
  const retryTimerRef = useRef<number | null>(null);

  const pingDatabase = useCallback(async () => {
    setState("checking");
    try {
      const response = await apiFetch(`${API_BASE}/health/db`, {
        timeoutMs: WARMUP_TIMEOUT_MS,
      });
      if (response.ok) {
        setState("ok");
        return;
      }
      setState("unavailable");
    } catch {
      setState("unavailable");
    }
  }, []);

  useEffect(() => {
    if (!isProductionApp) return;

    void pingDatabase();

    return () => {
      if (retryTimerRef.current !== null) {
        window.clearInterval(retryTimerRef.current);
      }
    };
  }, [pingDatabase]);

  useEffect(() => {
    if (!isProductionApp || state !== "unavailable") {
      if (retryTimerRef.current !== null) {
        window.clearInterval(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      return;
    }

    retryTimerRef.current = window.setInterval(() => {
      void pingDatabase();
    }, RETRY_INTERVAL_MS);

    return () => {
      if (retryTimerRef.current !== null) {
        window.clearInterval(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [pingDatabase, state]);

  const visible =
    isProductionApp && (state === "checking" || state === "unavailable");

  useEffect(() => {
    onVisibleChange?.(visible);
  }, [onVisibleChange, visible]);

  if (!visible) return null;

  const checking = state === "checking";

  return (
    <div
      role="status"
      className="fixed inset-x-0 top-0 z-[60] border-b border-amber-500/30 bg-amber-950/90 px-4 py-2.5 text-center text-sm text-amber-100 backdrop-blur-sm"
    >
      <div className="mx-auto flex max-w-4xl items-center justify-center gap-2">
        {checking ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-amber-300" />
        ) : (
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-300" />
        )}
        <p>
          {checking
            ? "Waking up database (free-tier cold start). This can take up to a minute…"
            : "Database is still waking up. Login and sync may fail — we retry automatically."}
        </p>
      </div>
    </div>
  );
}
