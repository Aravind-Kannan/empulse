"use client";

import { createPortal } from "react-dom";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";

import { fetchEraEmployeeDetail } from "@/lib/api";
import type {
  EraAnalyticsResponse,
  EraDimensionKey,
  EraEmployeeDetailResponse,
} from "@/lib/types";

import { EraDetailCompactInsights } from "./EraDetailCompactInsights";
import { EraBackupCandidates } from "./EraBackupCandidates";
import { EraHotspotSummary } from "./EraHotspotSummary";
import { EraReviewNetwork } from "./EraReviewNetwork";
import { EraMitigationChecklist } from "./EraMitigationChecklist";
import { EraDetailFooter } from "./EraDetailFooter";
import { EraDetailHero } from "./EraDetailHero";
import { EraContinuityRiskVisual } from "./EraContinuityRiskVisual";
import { trendDimensionsForChart } from "./era-utils";

interface EraDetailDrawerProps {
  employeeId: string;
  syncFreshness: EraAnalyticsResponse["sync_freshness"];
  demoMode: boolean;
  initialDimensionFilter?: EraDimensionKey | null;
  onClose: () => void;
}

export function EraDetailDrawer({
  employeeId,
  syncFreshness,
  demoMode,
  initialDimensionFilter = null,
  onClose,
}: EraDetailDrawerProps) {
  const [detail, setDetail] = useState<EraEmployeeDetailResponse | null>(null);
  const [filterDimensions, setFilterDimensions] = useState<EraDimensionKey[]>(
    initialDimensionFilter ? [initialDimensionFilter] : [],
  );
  const [expandedFactorId, setExpandedFactorId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const handleClose = useCallback(() => {
    setVisible(false);
    window.setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
    const frame = window.requestAnimationFrame(() => setVisible(true));
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const loadDetail = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchEraEmployeeDetail(employeeId, { limit: 100 })
      .then((response) => {
        setDetail(response);
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to load employee detail",
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [employeeId]);

  useEffect(() => {
    setFilterDimensions(initialDimensionFilter ? [initialDimensionFilter] : []);
    setExpandedFactorId(null);
  }, [employeeId, initialDimensionFilter]);

  const trendDimensions = useMemo((): EraDimensionKey[] => {
    if (!detail?.employee) {
      return initialDimensionFilter ? [initialDimensionFilter] : ["knowledge"];
    }
    return trendDimensionsForChart(detail.employee, filterDimensions);
  }, [detail?.employee, filterDimensions, initialDimensionFilter]);

  function handleGaugeClick(key: EraDimensionKey) {
    setFilterDimensions((current) => {
      if (current.includes(key)) {
        return current.filter((item) => item !== key);
      }
      return current.length === 0 ? [key] : [...current, key];
    });
    setExpandedFactorId(null);
  }

  function handleFactorClick(rowId: string) {
    setExpandedFactorId((current) => (current === rowId ? null : rowId));
  }

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        handleClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleClose]);

  function handleExportPdf() {
    window.print();
  }

  async function handleCopyLink() {
    const url = `${window.location.origin}/era?employee=${encodeURIComponent(employeeId)}`;
    try {
      await navigator.clipboard.writeText(url);
      setLinkCopied(true);
      window.setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      setLinkCopied(false);
    }
  }

  if (!mounted) return null;

  const content = (
    <>
      <button
        type="button"
        aria-label="Close employee detail"
        className="fixed inset-0 z-40 bg-black/50 print:hidden"
        onClick={handleClose}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Employee risk detail"
        className={`era-detail-drawer fixed right-0 top-0 z-50 flex h-full w-full max-w-2xl flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-200 ease-out print:static print:max-w-none print:border-0 print:shadow-none ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4 print:border-zinc-300">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              Employee profile
            </p>
            <h2 className="text-lg font-semibold text-zinc-100 print:text-black">
              {detail?.employee.name ?? "Loading…"}
            </h2>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 print:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {demoMode && (
          <div className="border-b border-amber-500/30 bg-amber-500/10 px-5 py-2 text-xs text-amber-200">
            Demo data — connect integrations for live continuity signals.
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {loading && (
            <div className="flex h-48 items-center justify-center text-zinc-400">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading profile…
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
              {error}
              <button
                type="button"
                onClick={handleClose}
                className="mt-3 block text-xs font-medium text-red-200 underline"
              >
                Close
              </button>
            </div>
          )}

          {!loading && !error && detail && (
            <div className="space-y-4">
              {detail.employee.excluded ? (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 text-center">
                  <h3 className="text-lg font-medium text-zinc-100">
                    Not applicable for ERA
                  </h3>
                  <p className="mt-2 text-sm text-zinc-400">
                    {detail.employee.exclusion_reason === "leadership_role"
                      ? "Leadership roles are excluded from individual ERA scoring."
                      : "This employee is outside ERA scope."}
                  </p>
                  <p className="mt-3 text-xs text-zinc-500">
                    View team roll-up metrics on the command center instead.
                  </p>
                </div>
              ) : (
                <>
                  <EraDetailHero
                    employee={detail.employee}
                    identityMappings={detail.identity_mappings}
                  />
                  <EraContinuityRiskVisual
                    employee={detail.employee}
                    evidence={detail.evidence}
                    evidenceTotalCount={detail.evidence_total_count}
                    filterDimensions={filterDimensions}
                    expandedFactorId={expandedFactorId}
                    onGaugeClick={handleGaugeClick}
                    onFactorClick={handleFactorClick}
                  />
                  <EraDetailCompactInsights
                    history={detail.risk_history_30d ?? []}
                    trendDimensions={trendDimensions}
                    components={detail.employee.affected_components ?? []}
                  />
                  <EraHotspotSummary
                    employeeId={detail.employee.employee_id}
                    employeeName={detail.employee.name}
                  />
                  <EraReviewNetwork
                    employeeId={detail.employee.employee_id}
                    employeeName={detail.employee.name}
                  />
                  <EraBackupCandidates candidates={detail.backup_candidates ?? []} />

                  <EraMitigationChecklist
                    employeeId={detail.employee.employee_id}
                    items={detail.mitigations ?? []}
                    onUpdated={() => void loadDetail()}
                  />
                </>
              )}
            </div>
          )}
        </div>

        {!loading && !error && detail && !detail.employee.excluded && (
          <EraDetailFooter
            employee={detail.employee}
            syncFreshness={syncFreshness}
            onExportPdf={handleExportPdf}
            onCopyLink={handleCopyLink}
            linkCopied={linkCopied}
          />
        )}
      </aside>

      <style jsx global>{`
        @media print {
          body * {
            visibility: hidden;
          }
          .era-detail-drawer,
          .era-detail-drawer * {
            visibility: visible;
          }
          .era-detail-drawer {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            max-width: none;
            height: auto;
            overflow: visible;
            background: white;
            color: black;
          }
          .era-detail-drawer .text-zinc-100,
          .era-detail-drawer .text-zinc-200 {
            color: #18181b !important;
          }
          .era-detail-drawer .text-zinc-400,
          .era-detail-drawer .text-zinc-500 {
            color: #52525b !important;
          }
        }
      `}</style>
    </>
  );

  return createPortal(content, document.body);
}
