"use client";

import type { EraEmployeeMetrics } from "@/lib/types";

import { EraDimensionRadar } from "./EraDimensionRadar";
import { EraEvidenceCard } from "./EraEvidenceCard";
import { dimensionValue } from "./era-utils";

interface EraEmployeePreviewProps {
  employee: EraEmployeeMetrics | null;
  onOpenDetail?: () => void;
}

function defaultDimensions(employee: EraEmployeeMetrics) {
  return {
    knowledge: dimensionValue(employee, "knowledge"),
    operational: dimensionValue(employee, "operational"),
    documentation: dimensionValue(employee, "documentation"),
    structural: dimensionValue(employee, "structural"),
    burnout: dimensionValue(employee, "burnout"),
  };
}

export function EraEmployeePreview({
  employee,
  onOpenDetail,
}: EraEmployeePreviewProps) {
  if (!employee) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h2 className="text-sm font-medium text-zinc-200">Top risk preview</h2>
        <p className="mt-4 text-sm text-zinc-500">Select an employee from the heatmap.</p>
      </div>
    );
  }

  const dimensions = employee.dimensions ?? defaultDimensions(employee);
  const topEvidence = (employee.evidence ?? []).slice(0, 3);
  const score = employee.risk_factor_score;
  const ringRadius = 36;
  const circumference = 2 * Math.PI * ringRadius;
  const dash = (score / 100) * circumference;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <h2 className="text-sm font-medium text-zinc-200">Top risk preview</h2>
      <div className="mt-4 flex items-center gap-4">
        <div className="relative h-24 w-24 shrink-0">
          <svg className="h-24 w-24 -rotate-90" viewBox="0 0 96 96">
            <circle
              cx="48"
              cy="48"
              r={ringRadius}
              fill="none"
              stroke="#27272a"
              strokeWidth="8"
            />
            <circle
              cx="48"
              cy="48"
              r={ringRadius}
              fill="none"
              stroke="#a78bfa"
              strokeWidth="8"
              strokeDasharray={`${dash} ${circumference}`}
              className="motion-safe:transition-all motion-reduce:transition-none"
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-zinc-100">
            {score}%
          </span>
        </div>
        <div>
          <p className="font-medium text-zinc-100">{employee.name}</p>
          <p className="text-xs text-zinc-500">{employee.role}</p>
        </div>
      </div>

      <div className="mt-4">
        <EraDimensionRadar dimensions={dimensions} size={160} />
      </div>

      <div className="mt-4 space-y-2">
        {topEvidence.length > 0 ? (
          topEvidence.map((item) => (
            <EraEvidenceCard key={item.id} item={item} compact />
          ))
        ) : (
          <p className="text-xs text-zinc-500">No evidence items yet for this employee.</p>
        )}
      </div>

      <button
        type="button"
        onClick={onOpenDetail}
        disabled={!onOpenDetail}
        className="mt-4 text-xs font-medium text-violet-300 hover:text-violet-200 disabled:cursor-not-allowed disabled:opacity-40"
      >
        View full profile →
      </button>
    </div>
  );
}
