"use client";

import { Plug } from "lucide-react";

import { IntegrationsDirectory } from "./IntegrationsDirectory";

export function IntegrationsPage() {
  return (
    <div className="mx-auto max-w-5xl p-6 lg:p-8">
      <header className="mb-6">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
            <Plug className="h-6 w-6 text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Integrations
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">
              Connect engineering tools and sync metadata into your Cognee
              knowledge graph.
            </p>
          </div>
        </div>
      </header>

      <IntegrationsDirectory showSyncToolbar />
    </div>
  );
}
