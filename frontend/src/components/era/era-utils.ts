import type {
  EraAnalyticsResponse,
  EraDimensionKey,
  EraDimensionSummary,
  EraEmployeeMetrics,
  EraEvidenceItem,
  EraRiskHistoryPoint,
  IntegrationId,
} from "@/lib/types";

import { apiDateToEpochMs } from "@/lib/datetime";

import { DIMENSION_KEYS, ERA_DIMENSION_COLORS } from "./era-colors";

export interface TeamEvidenceItem extends EraEvidenceItem {
  employee_id: string;
  employee_name: string;
}

export function buildTeamEvidenceFeed(
  employees: EraEmployeeMetrics[],
  teamEvidence: EraEvidenceItem[] = [],
  limit?: number,
): TeamEvidenceItem[] {
  const flat: TeamEvidenceItem[] = teamEvidence.map((item) => ({
    ...item,
    employee_id: "_team",
    employee_name: "Team",
  }));
  for (const employee of employees) {
    for (const item of employee.evidence ?? []) {
      flat.push({
        ...item,
        employee_id: employee.employee_id,
        employee_name: employee.name,
      });
    }
  }
  const sorted = flat.sort((a, b) => b.impact_points - a.impact_points);
  if (limit === undefined) {
    return sorted;
  }
  return sorted.slice(0, limit);
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
    .map((value) => apiDateToEpochMs(value))
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

export function highestDimensionKey(
  employee: EraEmployeeMetrics,
): EraDimensionKey {
  return DIMENSION_KEYS.reduce((best, key) =>
    dimensionValue(employee, key) > dimensionValue(employee, best) ? key : best,
  );
}

export function trendDimensionsForChart(
  employee: EraEmployeeMetrics,
  filterDimensions: EraDimensionKey[],
): EraDimensionKey[] {
  if (filterDimensions.length > 0) {
    return filterDimensions;
  }
  return [highestDimensionKey(employee)];
}

export function teamTrendDimensionsForChart(
  topDriver: EraDimensionKey,
  filterDimensions: EraDimensionKey[],
): EraDimensionKey[] {
  if (filterDimensions.length > 0) {
    return filterDimensions;
  }
  return [topDriver];
}

export function historyForDimension(
  history: EraRiskHistoryPoint[],
  dimension: EraDimensionKey,
): EraRiskHistoryPoint[] {
  return history.map((point) => ({
    snapshot_date: point.snapshot_date,
    risk_factor_score: point.dimensions?.[dimension] ?? 0,
  }));
}

export function isDimensionPartial(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
): boolean {
  return Boolean(
    employee.dimension_summaries?.[key]?.partial
      ?? employee.dimensions?.partial?.[key],
  );
}

export function getDimensionSummary(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
): EraDimensionSummary | null {
  return employee.dimension_summaries?.[key] ?? null;
}

export function dimensionHeadline(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
): string {
  const summary = getDimensionSummary(employee, key);
  if (summary?.headline) return summary.headline;
  const evidence = topEvidenceForDimension(employee, key)[0];
  if (evidence) return evidence.title;
  if (isDimensionPartial(employee, key)) {
    return "Partial data — connect more integrations";
  }
  if (dimensionValue(employee, key) <= 0) {
    return "No significant signal";
  }
  return "Low contribution from available signals";
}

export function topEvidenceForDimension(
  employee: EraEmployeeMetrics,
  key: EraDimensionKey,
  limit = 2,
): EraEvidenceItem[] {
  return (employee.evidence ?? [])
    .filter((item) => item.dimension === key)
    .sort((a, b) => b.impact_points - a.impact_points)
    .slice(0, limit);
}

export function buildCompositeRiskSentence(
  employee: EraEmployeeMetrics,
): string {
  const score = Math.round(employee.risk_factor_score);
  const primary = primaryDimensionKey(employee);
  const primaryLabel = ERA_DIMENSION_COLORS[primary].label;
  const headline = dimensionHeadline(employee, primary);
  const secondary = DIMENSION_KEYS.filter((key) => key !== primary)
    .map((key) => ({ key, value: dimensionValue(employee, key) }))
    .sort((a, b) => b.value - a.value)[0];
  if (secondary && secondary.value >= 30 && secondary.value >= dimensionValue(employee, primary) * 0.6) {
    const secondaryLabel = ERA_DIMENSION_COLORS[secondary.key].label;
    const secondaryHeadline = dimensionHeadline(employee, secondary.key);
    return `${score}% continuity risk — mainly ${primaryLabel} (${headline}) and ${secondaryLabel} (${secondaryHeadline}).`;
  }
  return `${score}% continuity risk — mainly ${primaryLabel}: ${headline}.`;
}

export function identityCoverageSummary(
  employee: EraEmployeeMetrics,
): { connected: number; total: number; missing: IntegrationId[] } {
  const providers: IntegrationId[] = ["github", "jira", "slack", "notion"];
  const coverage = employee.identity_coverage ?? {};
  const missing = providers.filter(
    (provider) => (coverage[provider] ?? "missing") === "missing",
  );
  return {
    connected: providers.length - missing.length,
    total: providers.length,
    missing,
  };
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

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function primaryDimensionKey(
  employee: EraEmployeeMetrics,
): EraDimensionKey {
  let best: EraDimensionKey = "knowledge";
  let bestValue = -1;
  for (const key of DIMENSION_KEYS) {
    const value = dimensionValue(employee, key);
    if (value > bestValue) {
      bestValue = value;
      best = key;
    }
  }
  return best;
}

const INTEGRATION_LABELS: Record<IntegrationId, string> = {
  github: "GitHub",
  jira: "Jira",
  slack: "Slack",
  notion: "Notion",
};

const ERA_WARNING_MESSAGES: Record<string, string> = {
  github_not_synced:
    "GitHub is connected but not synced — Knowledge and Structural scores use org chart only.",
  github_stale: "GitHub sync is stale — dimension scores may be outdated.",
  jira_not_synced:
    "Jira is connected but not synced — Operational scores may be incomplete.",
  jira_stale: "Jira sync is stale — Operational scores may be outdated.",
  partial_identity:
    "Some activity could not be mapped to employees — scores may be understated.",
  era_dimensions_partial:
    "Sync GitHub, Jira, and Notion for full K/O/D/S/B dimension coverage.",
};

export function formatEraWarning(code: string): string {
  return ERA_WARNING_MESSAGES[code] ?? code.replaceAll("_", " ");
}

export function formatProviderSyncAge(iso: string | null | undefined): string {
  if (!iso) return "never";
  const minutes = Math.round((Date.now() - apiDateToEpochMs(iso)) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export function formatPerProviderSyncFreshness(
  syncFreshness: EraAnalyticsResponse["sync_freshness"],
): string {
  const providers: IntegrationId[] = ["github", "jira", "slack", "notion"];
  return providers
    .map(
      (provider) =>
        `${INTEGRATION_LABELS[provider]} ${formatProviderSyncAge(syncFreshness[provider])}`,
    )
    .join(" · ");
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
