"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  History,
  Plug,
} from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { formatRelativeTime } from "@/lib/datetime";
import { getConnectedIntegrationIds } from "@/lib/integrations";
import {
  aggregateWorkspaceSyncStats,
  formatSyncChangeSummary,
  sourcesNeedingAttention,
} from "@/lib/sync-jobs";

import { IntegrationStatCard } from "./IntegrationStatCard";

export function IntegrationsStatsRow() {
  const { config, syncJobs } = useIntegrations();
  const connectedCount = getConnectedIntegrationIds(config).length;
  const stats = useMemo(() => aggregateWorkspaceSyncStats(syncJobs), [syncJobs]);
  const attention = useMemo(
    () => sourcesNeedingAttention(config, syncJobs),
    [config, syncJobs],
  );

  const lastSyncValue =
    stats.completedCount > 0
      ? formatSyncChangeSummary(
          stats.newItems,
          stats.updatedItems,
          stats.skippedItems,
        )
      : "—";

  const lastSyncHint =
    stats.lastCompletedAt != null
      ? `Last completed ${formatRelativeTime(stats.lastCompletedAt)}`
      : connectedCount > 0
        ? "Run sync to import data"
        : "Link a source first";

  const attentionHint =
    connectedCount === 0
      ? "Link a source to begin"
      : attention.count === 0
        ? "All sources healthy"
        : attention.labels.slice(0, 3).join(", ") +
          (attention.labels.length > 3 ? ` +${attention.labels.length - 3}` : "");

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <IntegrationStatCard
        icon={Plug}
        label="Sources linked"
        value={connectedCount}
        hint="Add only the tools you use"
      />
      <IntegrationStatCard
        icon={History}
        label="Last sync"
        value={lastSyncValue}
        hint={lastSyncHint}
        compactValue
        info="New and updated items imported into the knowledge graph. Unchanged items were already stored and not re-imported."
      />
      <IntegrationStatCard
        icon={attention.count > 0 ? AlertTriangle : CheckCircle2}
        label="Needs attention"
        value={connectedCount === 0 ? "—" : attention.count}
        hint={attentionHint}
      />
    </div>
  );
}
