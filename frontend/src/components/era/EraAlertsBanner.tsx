"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Bell, Check, Loader2 } from "lucide-react";

import {
  acknowledgeEraAlert,
  fetchEraAlerts,
  fetchEraReviewCadence,
  recordEraTeamReview,
} from "@/lib/api";
import type { EraAlertItem, EraReviewCadenceResponse } from "@/lib/types";

interface EraAlertsBannerProps {
  onUpdated?: () => void;
}

function severityClass(severity: string) {
  if (severity === "critical") {
    return "border-red-500/40 bg-red-500/10 text-red-200";
  }
  if (severity === "high") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  }
  return "border-sky-500/40 bg-sky-500/10 text-sky-200";
}

function alertActionLink(alert: EraAlertItem): string | null {
  if (alert.rule_id === "identity_gap") {
    return "/settings/identity-mapping";
  }
  if (alert.rule_id === "stale_sync") {
    return "/settings/integrations";
  }
  return "/era";
}

export function EraAlertsBanner({ onUpdated }: EraAlertsBannerProps) {
  const [alerts, setAlerts] = useState<EraAlertItem[]>([]);
  const [cadence, setCadence] = useState<EraReviewCadenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAlertId, setPendingAlertId] = useState<number | null>(null);
  const [pendingReview, setPendingReview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [alertsResponse, cadenceResponse] = await Promise.all([
        fetchEraAlerts({ unacknowledged: true }),
        fetchEraReviewCadence(),
      ]);
      setAlerts(alertsResponse.alerts);
      setCadence(cadenceResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ERA alerts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAcknowledge(alertId: number) {
    setPendingAlertId(alertId);
    try {
      await acknowledgeEraAlert(alertId);
      await load();
      onUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge alert.");
    } finally {
      setPendingAlertId(null);
    }
  }

  async function handleMarkReviewed() {
    setPendingReview(true);
    try {
      await recordEraTeamReview({ notes: "Monthly ERA knowledge risk review completed." });
      await load();
      onUpdated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record review.");
    } finally {
      setPendingReview(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/30 px-3 py-2 text-xs text-zinc-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading ERA alerts…
      </div>
    );
  }

  const showReviewBanner = cadence?.review_overdue ?? false;
  const showAlerts = alerts.length > 0;

  if (!showReviewBanner && !showAlerts && !error) {
    return null;
  }

  return (
    <section className="space-y-2">
      {error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </div>
      ) : null}

      {showReviewBanner && cadence ? (
        <div className="flex flex-col gap-3 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2 text-sm text-violet-100">
            <Bell className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Knowledge risk review due</p>
              <p className="mt-1 text-xs text-violet-200/80">
                {cadence.last_reviewed_at
                  ? `Last team risk review: ${cadence.days_since_last_review ?? 0} days ago`
                  : "No team risk review recorded yet"}
                {cadence.snapshot_avg_risk != null
                  ? ` — team avg risk ${Math.round(cadence.snapshot_avg_risk)}%`
                  : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            disabled={pendingReview}
            onClick={() => void handleMarkReviewed()}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-violet-400/40 bg-violet-500/20 px-3 py-1.5 text-xs font-medium text-violet-100 hover:bg-violet-500/30 disabled:opacity-50"
          >
            {pendingReview ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Mark reviewed
          </button>
        </div>
      ) : null}

      {showAlerts ? (
        <div className="space-y-2">
          {alerts.slice(0, 5).map((alert) => {
            const actionHref = alertActionLink(alert);
            return (
              <div
                key={alert.id}
                className={`flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-start sm:justify-between ${severityClass(alert.severity)}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    <p className="text-sm font-medium">{alert.title}</p>
                  </div>
                  <p className="mt-1 text-xs opacity-90">{alert.description}</p>
                  <p className="mt-1 text-[10px] uppercase tracking-wide opacity-70">
                    Team channel alert · {alert.rule_id.replaceAll("_", " ")}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {actionHref ? (
                    <Link
                      href={actionHref}
                      className="rounded-md border border-current/30 px-2.5 py-1 text-xs hover:bg-black/10"
                    >
                      View
                    </Link>
                  ) : null}
                  <button
                    type="button"
                    disabled={pendingAlertId === alert.id}
                    onClick={() => void handleAcknowledge(alert.id)}
                    className="rounded-md border border-current/30 px-2.5 py-1 text-xs hover:bg-black/10 disabled:opacity-50"
                  >
                    {pendingAlertId === alert.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      "Acknowledge"
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
