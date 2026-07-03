"use client";

import { useEffect, useState } from "react";

import {
  isSyncJobActive,
  syncDurationLabel,
} from "@/lib/sync-duration";
import type { IntegrationSyncJobStatusResponse } from "@/lib/types";

interface SyncDurationProps {
  job: Pick<
    IntegrationSyncJobStatusResponse,
    "created_at" | "completed_at" | "duration_seconds" | "status"
  >;
  className?: string;
}

/** Live elapsed timer for active syncs; wall-clock duration when finished. */
export function SyncDuration({ job, className = "" }: SyncDurationProps) {
  const live = isSyncJobActive(job.status);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!live) {
      return;
    }
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [live]);

  const label = syncDurationLabel(job, nowMs);
  if (!label) {
    return null;
  }

  return (
    <span
      className={`inline-flex items-center gap-1 tabular-nums ${className}`}
      title={live ? "Time since sync was queued" : "Total sync wall time"}
    >
      {live && (
        <span
          className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-sky-400/80"
          aria-hidden
        />
      )}
      {label}
    </span>
  );
}
