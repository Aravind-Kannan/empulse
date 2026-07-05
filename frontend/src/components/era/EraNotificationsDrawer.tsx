"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Bell, Check, Loader2 } from "lucide-react";

import {
  acknowledgeEraAlert,
  fetchEraAlerts,
  fetchEraReviewCadence,
  recordEraTeamReview,
} from "@/lib/api";
import type { EraAlertItem, EraReviewCadenceResponse } from "@/lib/types";

import { EraSidePanel } from "./EraSidePanel";
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

function severityBadgeClass(severity: string): string {
  if (severity === "critical") {
    return "border-red-500/30 bg-red-500/15 text-red-200";
  }
  if (severity === "high") {
    return "border-amber-500/30 bg-amber-500/15 text-amber-200";
  }
  return "border-sky-500/30 bg-sky-500/15 text-sky-200";
}

function warningActionLink(code: string): string | null {
  if (code === "partial_identity") {
    return "/settings/org-chart?tab=identity";
  }
  if (
    code === "github_not_synced" ||
    code === "github_stale" ||
    code === "jira_not_synced" ||
    code === "jira_stale" ||
    code === "era_dimensions_partial"
  ) {
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
  if (alert.rule_id === "unassigned_p1" || alert.rule_id === "spof_tier1") {
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

function NotificationRow({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "warn" | "violet";
}) {
  const toneClass =
    tone === "warn"
      ? "border-amber-500/25 bg-amber-500/5"
      : tone === "violet"
        ? "border-violet-500/25 bg-violet-500/5"
        : "border-zinc-800/60 bg-zinc-950/30";

  return (
    <li className={`rounded border px-2.5 py-2 ${toneClass}`}>{children}</li>
  );
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

  if (!mounted) return null;

  const showReviewBanner = cadence?.review_overdue ?? false;
  const showUnmappedExtra =
    unmappedCount > 0 && !warnings.includes("partial_identity");
  const itemCount =
    warnings.length +
    (showUnmappedExtra ? 1 : 0) +
    (showReviewBanner ? 1 : 0) +
    alerts.length;

  return (
    <EraSidePanel
      open={open}
      visible={visible}
      onClose={handleClose}
      eyebrow="Operational signals"
      title="Alerts & notifications"
      subtitle={
        loading
          ? "Loading…"
          : `${itemCount} active item${itemCount === 1 ? "" : "s"}`
      }
      ariaLabel="ERA notifications"
      closeButtonRef={closeButtonRef}
      maxWidth="md"
      footer={
        onOpenAlertsSettings ? (
          <button
            type="button"
            onClick={onOpenAlertsSettings}
            className="text-[11px] font-medium text-violet-300 hover:text-violet-200"
          >
            Configure alert rules
          </button>
        ) : undefined
      }
    >
      {error ? (
        <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[11px] text-red-300">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-[11px] text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading notifications…
        </div>
      ) : (
        <>
          {itemCount === 0 ? (
            <p className="py-8 text-center text-[11px] text-zinc-500">
              No active notifications.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {warnings.map((warning) => {
                const actionHref = warningActionLink(warning);
                return (
                  <NotificationRow key={warning} tone="warn">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[11px] leading-snug text-amber-100">
                          {formatEraWarning(warning)}
                        </p>
                        {warning === "partial_identity" && unmappedCount > 0 ? (
                          <p className="mt-1 text-[10px] text-amber-200/80">
                            {unmappedCount} unmapped activity event
                            {unmappedCount === 1 ? "" : "s"} in queue.
                          </p>
                        ) : null}
                        {actionHref ? (
                          <Link
                            href={actionHref}
                            className="mt-1.5 inline-block text-[10px] font-medium text-amber-200 hover:text-amber-100"
                          >
                            Open settings →
                          </Link>
                        ) : null}
                      </div>
                    </div>
                  </NotificationRow>
                );
              })}

              {showUnmappedExtra ? (
                <NotificationRow tone="warn">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
                    <div>
                      <p className="text-[11px] leading-snug text-amber-100">
                        {unmappedCount} unmapped activity event
                        {unmappedCount === 1 ? "" : "s"} — scores may be understated.
                      </p>
                      <Link
                        href="/settings/org-chart?tab=identity"
                        className="mt-1.5 inline-block text-[10px] font-medium text-amber-200 hover:text-amber-200"
                      >
                        Open identity mapping →
                      </Link>
                    </div>
                  </div>
                </NotificationRow>
              ) : null}

              {showReviewBanner && cadence ? (
                <NotificationRow tone="violet">
                  <div className="flex items-start gap-2">
                    <Bell className="mt-0.5 h-3.5 w-3.5 shrink-0 text-violet-300" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-medium text-violet-100">
                        Knowledge risk review due
                      </p>
                      <p className="mt-1 text-[10px] text-violet-200/80">
                        {cadence.last_reviewed_at
                          ? `Last team risk review: ${cadence.days_since_last_review ?? 0} days ago`
                          : "No team risk review recorded yet"}
                        {cadence.snapshot_avg_risk != null
                          ? ` — team avg risk ${Math.round(cadence.snapshot_avg_risk)}%`
                          : ""}
                      </p>
                      <button
                        type="button"
                        disabled={pendingReview}
                        onClick={() => void handleMarkReviewed()}
                        className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-[10px] font-medium text-violet-100 hover:bg-violet-500/20 disabled:opacity-50"
                      >
                        {pendingReview ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Check className="h-3 w-3" />
                        )}
                        Mark reviewed
                      </button>
                    </div>
                  </div>
                </NotificationRow>
              ) : null}

              {alerts.map((alert) => {
                const actionHref = alertActionLink(alert);
                const useCallback = Boolean(onViewAlert && alertViewUsesCallback(alert));
                const showView = useCallback || Boolean(actionHref);

                return (
                  <NotificationRow key={alert.id}>
                    <div className="flex min-w-0 flex-1 flex-col gap-2">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[9px] font-medium uppercase ${severityBadgeClass(alert.severity)}`}
                          >
                            {alert.severity}
                          </span>
                          <p className="text-[11px] font-medium text-zinc-200">
                            {alert.title}
                          </p>
                        </div>
                        <p className="mt-1 text-[10px] leading-snug text-zinc-400">
                          {alert.description}
                        </p>
                        <p className="mt-1 text-[9px] uppercase tracking-wide text-zinc-600">
                          {alert.rule_id.replaceAll("_", " ")}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {showView ? (
                          useCallback ? (
                            <button
                              type="button"
                              onClick={() => onViewAlert?.(alert)}
                              className="rounded-md border border-zinc-700/80 px-2 py-0.5 text-[10px] text-zinc-300 hover:border-zinc-600 hover:text-zinc-100"
                            >
                              View
                            </button>
                          ) : (
                            <Link
                              href={actionHref!}
                              onClick={handleClose}
                              className="rounded-md border border-zinc-700/80 px-2 py-0.5 text-[10px] text-zinc-300 hover:border-zinc-600 hover:text-zinc-100"
                            >
                              View
                            </Link>
                          )
                        ) : null}
                        <button
                          type="button"
                          disabled={pendingAlertId === alert.id}
                          onClick={() => void handleAcknowledge(alert.id)}
                          className="rounded-md border border-zinc-700/80 px-2 py-0.5 text-[10px] text-zinc-300 hover:border-zinc-600 hover:text-zinc-100 disabled:opacity-50"
                        >
                          {pendingAlertId === alert.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            "Acknowledge"
                          )}
                        </button>
                      </div>
                    </div>
                  </NotificationRow>
                );
              })}
            </ul>
          )}
        </>
      )}
    </EraSidePanel>
  );
}
