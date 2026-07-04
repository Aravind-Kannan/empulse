"use client";

import Link from "next/link";
import { createPortal } from "react-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Bell, Check, Loader2, X } from "lucide-react";

import {
  acknowledgeEraAlert,
  fetchEraAlerts,
  fetchEraReviewCadence,
  recordEraTeamReview,
} from "@/lib/api";
import type { EraAlertItem, EraReviewCadenceResponse } from "@/lib/types";

import { formatEraWarning } from "./era-utils";

interface EraNotificationsDrawerProps {
  open: boolean;
  onClose: () => void;
  warnings: string[];
  unmappedCount: number;
  onOpenAlertsSettings?: () => void;
  onViewAlert?: (alert: EraAlertItem) => void;
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

function warningActionLink(code: string): string | null {
  if (code === "partial_identity") {
    return "/settings/org-chart?tab=identity";
  }
  if (code === "github_not_synced" || code === "github_stale") {
    return "/settings/integrations";
  }
  if (code === "jira_not_synced" || code === "jira_stale") {
    return "/settings/integrations";
  }
  if (code === "era_dimensions_partial") {
    return "/settings/integrations";
  }
  return null;
}

function alertActionLink(alert: EraAlertItem): string | null {
  if (alert.rule_id === "identity_gap") {
    return "/settings/org-chart?tab=identity";
  }
  if (alert.rule_id === "stale_sync") {
    return "/settings/integrations";
  }
  if (alert.rule_id === "critical_file" && alert.employee_id) {
    return `/era?employee=${encodeURIComponent(alert.employee_id)}`;
  }
  if (alert.rule_id === "unassigned_p1") {
    return "/era";
  }
  if (alert.rule_id === "spof_tier1") {
    return "/era";
  }
  return null;
}

function alertViewUsesCallback(alert: EraAlertItem): boolean {
  if (alert.rule_id === "critical_file") {
    return Boolean(alert.employee_id);
  }
  return alert.rule_id === "unassigned_p1" || alert.rule_id === "spof_tier1";
}

export function eraNotificationCount(
  warnings: string[],
  unmappedCount: number,
  alertCount: number,
  reviewOverdue: boolean,
): number {
  let count = warnings.length + alertCount + (reviewOverdue ? 1 : 0);
  if (unmappedCount > 0 && !warnings.includes("partial_identity")) {
    count += 1;
  }
  return count;
}

export function EraNotificationsDrawer({
  open,
  onClose,
  warnings,
  unmappedCount,
  onOpenAlertsSettings,
  onViewAlert,
  onUpdated,
}: EraNotificationsDrawerProps) {
  const [alerts, setAlerts] = useState<EraAlertItem[]>([]);
  const [cadence, setCadence] = useState<EraReviewCadenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingAlertId, setPendingAlertId] = useState<number | null>(null);
  const [pendingReview, setPendingReview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

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

  const handleClose = useCallback(() => {
    setVisible(false);
    window.setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    void load();
    const frame = window.requestAnimationFrame(() => setVisible(true));
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, load]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        handleClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, handleClose]);

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

  if (!mounted || !open) return null;

  const showReviewBanner = cadence?.review_overdue ?? false;
  const showUnmappedExtra =
    unmappedCount > 0 && !warnings.includes("partial_identity");

  const content = (
    <>
      <button
        type="button"
        aria-label="Close notifications"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={handleClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="ERA notifications"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-200 ease-out ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">ERA</p>
            <h2 className="text-lg font-semibold text-zinc-100">Notifications</h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-5">
          {error ? (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {error}
            </div>
          ) : null}

          {loading ? (
            <div className="flex items-center gap-2 py-8 text-xs text-zinc-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Loading notifications…
            </div>
          ) : (
            <>
              {warnings.length === 0 &&
              !showUnmappedExtra &&
              !showReviewBanner &&
              alerts.length === 0 ? (
                <p className="py-8 text-center text-sm text-zinc-500">
                  No active notifications.
                </p>
              ) : null}

              {warnings.map((warning) => {
                const actionHref = warningActionLink(warning);
                return (
                  <div
                    key={warning}
                    className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3"
                  >
                    <div className="flex items-start gap-2 text-sm text-amber-100">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <div className="min-w-0">
                        <p>{formatEraWarning(warning)}</p>
                        {warning === "partial_identity" && unmappedCount > 0 ? (
                          <p className="mt-1 text-xs text-amber-200/80">
                            {unmappedCount} unmapped activity event
                            {unmappedCount === 1 ? "" : "s"} in queue.
                          </p>
                        ) : null}
                        {actionHref ? (
                          <Link
                            href={actionHref}
                            className="mt-2 inline-block text-xs font-medium text-amber-200 underline-offset-2 hover:underline"
                          >
                            Open settings
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  </div>
                );
              })}

              {showUnmappedExtra ? (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
                  <div className="flex items-start gap-2 text-sm text-amber-100">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p>
                        {unmappedCount} unmapped activity event
                        {unmappedCount === 1 ? "" : "s"} — scores may be understated.
                      </p>
                      <Link
                        href="/settings/org-chart?tab=identity"
                        className="mt-2 inline-block text-xs font-medium text-amber-200 underline-offset-2 hover:underline"
                      >
                        Open identity mapping
                      </Link>
                    </div>
                  </div>
                </div>
              ) : null}

              {showReviewBanner && cadence ? (
                <div className="flex flex-col gap-3 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-3">
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
                    className="inline-flex items-center justify-center gap-1.5 self-start rounded-md border border-violet-400/40 bg-violet-500/20 px-3 py-1.5 text-xs font-medium text-violet-100 hover:bg-violet-500/30 disabled:opacity-50"
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

              {alerts.map((alert) => {
                const actionHref = alertActionLink(alert);
                const useCallback = Boolean(onViewAlert && alertViewUsesCallback(alert));
                const showView = useCallback || Boolean(actionHref);
                return (
                  <div
                    key={alert.id}
                    className={`flex flex-col gap-3 rounded-lg border px-4 py-3 ${severityClass(alert.severity)}`}
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
                      {showView ? (
                        useCallback ? (
                          <button
                            type="button"
                            onClick={() => onViewAlert?.(alert)}
                            className="rounded-md border border-current/30 px-2.5 py-1 text-xs hover:bg-black/10"
                          >
                            View
                          </button>
                        ) : (
                          <Link
                            href={actionHref!}
                            onClick={handleClose}
                            className="rounded-md border border-current/30 px-2.5 py-1 text-xs hover:bg-black/10"
                          >
                            View
                          </Link>
                        )
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
            </>
          )}
        </div>

        {onOpenAlertsSettings ? (
          <div className="border-t border-zinc-800 px-5 py-4">
            <button
              type="button"
              onClick={onOpenAlertsSettings}
              className="text-xs font-medium text-violet-300 hover:text-violet-200"
            >
              Configure alert rules
            </button>
          </div>
        ) : null}
      </aside>
    </>
  );

  return createPortal(content, document.body);
}
