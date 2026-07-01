import type {
  EraAnalyticsResponse,
  EraDimensionKey,
  EraEmployeeMetrics,
  EraEvidenceItem,
  IntegrationId,
} from "@/lib/types";

import { DIMENSION_KEYS } from "./era-colors";

export interface TeamEvidenceItem extends EraEvidenceItem {
  employee_id: string;
  employee_name: string;
}

export function buildTeamEvidenceFeed(
  employees: EraEmployeeMetrics[],
  limit = 10,
): TeamEvidenceItem[] {
  const flat: TeamEvidenceItem[] = [];
  for (const employee of employees) {
    for (const item of employee.evidence ?? []) {
      flat.push({
        ...item,
        employee_id: employee.employee_id,
        employee_name: employee.name,
      });
    }
  }
  return flat
    .sort((a, b) => b.impact_points - a.impact_points)
    .slice(0, limit);
}

export function totalUnmappedCount(
  unmapped: EraAnalyticsResponse["unmapped_activity"],
): number {
  return unmapped.reduce((sum, row) => sum + row.count, 0);
}

export function connectedIntegrationCount(
  syncFreshness: EraAnalyticsResponse["sync_freshness"],
): number {
  const providers: IntegrationId[] = ["github", "jira", "slack", "notion"];
  return providers.filter((provider) => Boolean(syncFreshness[provider])).length;
}

export function formatSyncFreshness(
  syncFreshness: EraAnalyticsResponse["sync_freshness"],
): { label: string; tone: "ok" | "warn" | "stale" } {
  const timestamps = Object.values(syncFreshness).filter(Boolean) as string[];
  if (timestamps.length === 0) {
    return { label: "No sync yet", tone: "stale" };
  }
  const latest = timestamps
    .map((value) => new Date(value).getTime())
    .sort((a, b) => b - a)[0];
  const minutes = Math.round((Date.now() - latest) / 60000);
  if (minutes < 60) {
    return { label: `Last sync: ${minutes}m`, tone: "ok" };
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return { label: `Last sync: ${hours}h`, tone: hours < 6 ? "ok" : "warn" };
  }
  return { label: `Last sync: ${Math.round(hours / 24)}d`, tone: "stale" };
}

export function dimensionValue(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
): number {
  return employee.dimensions?.[key] ?? 0;
}

export function isDimensionPartial(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
): boolean {
  return Boolean(employee.dimensions?.partial?.[key]);
}

export function teamDimensionTotals(employees: EraEmployeeMetrics[]) {
  const totals = Object.fromEntries(
    DIMENSION_KEYS.map((key) => [key, 0]),
  ) as Record<EraDimensionKey, number>;
  const active = employees.filter((employee) => !employee.excluded);
  if (active.length === 0) return totals;
  for (const employee of active) {
    for (const key of DIMENSION_KEYS) {
      totals[key] += dimensionValue(employee, key);
    }
  }
  return totals;
}

export function riskBarClass(score: number): string {
  if (score > 75) return "from-red-500 to-red-400";
  if (score >= 40) return "from-amber-500 to-amber-400";
  return "from-emerald-500 to-emerald-400";
}

export function exportEmployeesCsv(employees: EraEmployeeMetrics[]) {
  const headers = [
    "employee_id",
    "name",
    "role",
    "risk_factor_score",
    "risk_level",
    "knowledge",
    "operational",
    "documentation",
    "structural",
    "burnout",
  ];
  const rows = employees.map((employee) =>
    [
      employee.employee_id,
      employee.name,
      employee.role,
      employee.risk_factor_score,
      employee.risk_level,
      dimensionValue(employee, "knowledge"),
      dimensionValue(employee, "operational"),
      dimensionValue(employee, "documentation"),
      dimensionValue(employee, "structural"),
      dimensionValue(employee, "burnout"),
    ].join(","),
  );
  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "era-team-export.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}
