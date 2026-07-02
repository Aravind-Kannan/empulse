import { Suspense } from "react";

import { KraDashboard } from "@/components/kra/KraDashboard";

function KraPageFallback() {
  return (
    <div className="flex h-64 items-center justify-center text-zinc-400">
      Loading knowledge graph…
    </div>
  );
}

export default function KraPage() {
  return (
    <div className="p-8">
      <Suspense fallback={<KraPageFallback />}>
        <KraDashboard />
      </Suspense>
    </div>
  );
}
