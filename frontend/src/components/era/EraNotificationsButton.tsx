"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, Loader2 } from "lucide-react";

import { fetchEraAlerts, fetchEraReviewCadence } from "@/lib/api";

import { eraNotificationCount } from "./EraNotificationsDrawer";

interface EraNotificationsButtonProps {
  warnings: string[];
  unmappedCount: number;
  refreshKey?: number;
  onClick: () => void;
}

export function EraNotificationsButton({
  warnings,
  unmappedCount,
  refreshKey = 0,
  onClick,
}: EraNotificationsButtonProps) {
  const [alertCount, setAlertCount] = useState(0);
  const [reviewOverdue, setReviewOverdue] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [alertsResponse, cadenceResponse] = await Promise.all([
        fetchEraAlerts({ unacknowledged: true }),
        fetchEraReviewCadence(),
      ]);
      setAlertCount(alertsResponse.alerts.length);
      setReviewOverdue(cadenceResponse.review_overdue);
    } catch {
      setAlertCount(0);
      setReviewOverdue(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const count = eraNotificationCount(
    warnings,
    unmappedCount,
    alertCount,
    reviewOverdue,
  );

  if (!loading && count === 0) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-300 hover:bg-amber-500/20 disabled:opacity-60"
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Bell className="h-3.5 w-3.5" />
      )}
      {loading ? "Alerts" : `${count} alert${count === 1 ? "" : "s"}`}
    </button>
  );
}
