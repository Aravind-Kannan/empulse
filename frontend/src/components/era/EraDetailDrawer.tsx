"use client";

import { createPortal } from "react-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";

import { fetchEraEmployeeDetail } from "@/lib/api";
import type {
  EraAnalyticsResponse,
  EraDimensionKey,
  EraEmployeeDetailResponse,
} from "@/lib/types";

import { EraAffectedComponentsGraph } from "./EraAffectedComponentsGraph";
import { EraBackupCandidates } from "./EraBackupCandidates";
import { EraDataQualityStrip } from "./EraDataQualityStrip";
import { EraHotspotSummary } from "./EraHotspotSummary";
import { EraReviewNetwork } from "./EraReviewNetwork";
import { EraMitigationChecklist } from "./EraMitigationChecklist";
import { EraDetailFooter } from "./EraDetailFooter";
import { EraDetailHero } from "./EraDetailHero";
import { EraDetailHistoryChart } from "./EraDetailHistoryChart";
import { EraDimensionFactorWaterfall } from "./EraDimensionFactorWaterfall";
import { EraDimensionGrid } from "./EraDimensionGrid";
import { EraDimensionRadar } from "./EraDimensionRadar";
import { EraEvidenceList } from "./EraEvidenceList";
import { EraRiskChart } from "./EraRiskChart";
import { buildCompositeRiskSentence, dimensionValue } from "./era-utils";

interface EraDetailDrawerProps {
  employeeId: string;
  syncFreshness: EraAnalyticsResponse["sync_freshness"];
  demoMode: boolean;
  initialDimensionFilter?: EraDimensionKey | null;
  onClose: () => void;
}

function defaultDimensions(detail: EraEmployeeDetailResponse) {
  const employee = detail.employee;
  return {
    knowledge: dimensionValue(employee, "knowledge"),
    operational: dimensionValue(employee, "operational"),
    documentation: dimensionValue(employee, "documentation"),
    structural: dimensionValue(employee, "structural"),
    burnout: dimensionValue(employee, "burnout"),
    partial: employee.dimensions?.partial,
  };
}

export function EraDetailDrawer({
  employeeId,
  syncFreshness,
  demoMode,
  initialDimensionFilter = null,
  onClose,
}: EraDetailDrawerProps) {
  const [detail, setDetail] = useState<EraEmployeeDetailResponse | null>(null);
  const [selectedDimensions, setSelectedDimensions] = useState<EraDimensionKey[]>(
    initialDimensionFilter ? [initialDimensionFilter] : [],
  );
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
    setSelectedDimensions(initialDimensionFilter ? [initialDimensionFilter] : []);
  }, [employeeId, initialDimensionFilter]);

  function toggleDimension(key: EraDimensionKey) {
    setSelectedDimensions((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    );
  }

  const filterLabel =
    selectedDimensions.length > 0
      ? ` (${selectedDimensions.length} selected)`
      : "";

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
            <div className="space-y-6">
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
                    blastRadiusNarrative={detail.blast_radius_narrative}
                  />
                  <p className="text-sm leading-relaxed text-zinc-400">
                    {buildCompositeRiskSentence(detail.employee)}
                  </p>
                  <EraDataQualityStrip employee={detail.employee} />
                  <EraDimensionGrid
                    employee={detail.employee}
                    selectedDimensions={selectedDimensions}
                    onToggleDimension={toggleDimension}
                  />
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
                    <h3 className="mb-3 text-sm font-medium text-zinc-200">
                      Score drivers{filterLabel}
                    </h3>
                    <EraDimensionFactorWaterfall
                      employee={detail.employee}
                      dimensions={selectedDimensions}
                    />
                  </div>
                  <EraEvidenceList
                    items={detail.evidence}
                    totalCount={detail.evidence_total_count}
                    employeeName={detail.employee.name}
                    filterDimensions={selectedDimensions}
                    defaultCollapsed
                  />
                  <EraDetailHistoryChart
                    history={detail.risk_history_30d ?? []}
                    employeeName={detail.employee.name}
                  />

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
                      <h3 className="mb-2 text-sm font-medium text-zinc-200">
                        Risk radar
                      </h3>
                      <EraDimensionRadar
                        dimensions={detail.employee.dimensions ?? defaultDimensions(detail)}
                        size={220}
                      />
                    </div>
                    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
                      <h3 className="mb-2 text-sm font-medium text-zinc-200">
                        Weighted breakdown
                      </h3>
                      <EraRiskChart employee={detail.employee} compact />
                    </div>
                  </div>

                  <EraAffectedComponentsGraph employee={detail.employee} />
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
