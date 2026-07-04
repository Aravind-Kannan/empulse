import { Suspense } from "react";

import { SettingsOrgChartPage } from "@/components/org-workspace/SettingsOrgChartPage";
import { WorkspacePageHeader } from "@/components/ui/WorkspacePageHeader";

function OrgChartPageFallback() {
  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        title="Organization Hub"
        subtitle="People, components, and identity mappings — your workspace command center."
      />
      <div className="grid max-w-md grid-cols-3 gap-3">
        {["People", "Components", "Teams"].map((label) => (
          <div
            key={label}
            className="h-16 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40"
          />
        ))}
      </div>
      <div className="h-12 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40" />
      <div className="h-[min(68vh,720px)] min-h-[480px] animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40" />
    </div>
  );
}

export default function OrgChartSettingsPage() {
  return (
    <div className="min-h-0 p-8">
      <Suspense fallback={<OrgChartPageFallback />}>
        <SettingsOrgChartPage />
      </Suspense>
    </div>
  );
}
