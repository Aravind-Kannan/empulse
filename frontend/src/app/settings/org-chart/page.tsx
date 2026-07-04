import { Suspense } from "react";

import { SettingsOrgChartPage } from "@/components/org-workspace/SettingsOrgChartPage";

function OrgChartPageFallback() {
  return (
    <div className="relative mx-auto max-w-7xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-gradient-to-b from-emerald-500/[0.07] to-transparent" />
      <div className="flex items-center gap-4">
        <div className="h-12 w-12 animate-pulse rounded-2xl bg-zinc-900/60" />
        <div className="space-y-2">
          <div className="h-3 w-24 animate-pulse rounded bg-zinc-900/50" />
          <div className="h-8 w-48 animate-pulse rounded-lg bg-zinc-900/50" />
        </div>
      </div>
      <div className="h-12 animate-pulse rounded-2xl bg-zinc-900/40" />
      <div className="h-[min(68vh,720px)] min-h-[480px] animate-pulse rounded-2xl bg-zinc-900/40" />
    </div>
  );
}

export default function OrgChartSettingsPage() {
  return (
    <Suspense fallback={<OrgChartPageFallback />}>
      <SettingsOrgChartPage />
    </Suspense>
  );
}
