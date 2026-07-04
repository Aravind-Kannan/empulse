"use client";

import { TenantSwitcher } from "@/components/settings/TenantSwitcher";
import { WorkspacePageHeader } from "@/components/ui/WorkspacePageHeader";

import { IntegrationsDirectory } from "./IntegrationsDirectory";

export function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        title="Integrations"
        subtitle="Connect engineering tools and sync metadata into your workspace knowledge graph."
      />

      <TenantSwitcher />

      <IntegrationsDirectory showSyncToolbar />
    </div>
  );
}
