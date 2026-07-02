"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { fetchEraEmployeeHotspots } from "@/lib/api";
import type { EraHotspotsResponse } from "@/lib/types";

import { FileRiskMatrix } from "@/components/kra/FileRiskMatrix";

interface EraHotspotSummaryProps {
  employeeId: string;
  employeeName: string;
}

export function EraHotspotSummary({
  employeeId,
  employeeName,
}: EraHotspotSummaryProps) {
  const [data, setData] = useState<EraHotspotsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchEraEmployeeHotspots(employeeId)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load file hotspots",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  if (loading) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading file hotspots…
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">File hotspots</h3>
        <p className="mt-2 text-sm text-red-300">{error}</p>
      </section>
    );
  }

  if (!data || data.files.length === 0) {
    return (
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h3 className="text-sm font-medium text-zinc-200">File hotspots</h3>
        <p className="mt-2 text-sm text-zinc-500">
          No critical file silos for {employeeName} in the last 90 days.
        </p>
      </section>
    );
  }

  return (
    <FileRiskMatrix
      title={`Critical files — ${employeeName}`}
      files={data.files}
      quadrantCounts={{ critical: data.critical_count }}
      crossTrainingPriority={data.files}
      compact
    />
  );
}
