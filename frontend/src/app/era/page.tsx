import { Suspense } from "react";

import { EraCommandCenter } from "@/components/era/EraCommandCenter";
import { EraDashboard } from "@/components/era/EraDashboard";
import { KnowledgeIngestionGate } from "@/components/sync/KnowledgeIngestionGate";

const useCommandCenter =
  process.env.NEXT_PUBLIC_ERA_COMMAND_CENTER !== "false";

function EraPageFallback() {
  return (
    <div className="space-y-6">
      <div className="h-16 animate-pulse rounded-xl bg-zinc-900/50" />
      <div className="h-48 animate-pulse rounded-xl bg-zinc-900/50" />
    </div>
  );
}

export default function EraPage() {
  return (
    <div className="p-4 md:p-8">
      <KnowledgeIngestionGate>
        {useCommandCenter ? (
          <Suspense fallback={<EraPageFallback />}>
            <EraCommandCenter />
          </Suspense>
        ) : (
          <EraDashboard />
        )}
      </KnowledgeIngestionGate>
    </div>
  );
}
