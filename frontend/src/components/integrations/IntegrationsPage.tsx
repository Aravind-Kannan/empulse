"use client";

import { TenantSwitcher } from "@/components/settings/TenantSwitcher";
import { WorkspacePageHeader } from "@/components/ui/WorkspacePageHeader";

import { IntegrationsDirectory } from "./IntegrationsDirectory";

export function IntegrationsPage() {
  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        title="Integrations"
        subtitle="Connect engineering tools, configure each source, and track sync history."
      />

      <TenantSwitcher />

      <IntegrationsDirectory showSyncToolbar />
    </div>
  );
}
