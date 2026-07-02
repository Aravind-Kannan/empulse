"use client";

import Link from "next/link";
import { ArrowLeft, Plug } from "lucide-react";

import { IntegrationsDirectory } from "./IntegrationsDirectory";

export function IntegrationsPage() {
  return (
    <div className="mx-auto max-w-5xl p-6 lg:p-8">
      <header className="mb-6 space-y-4">
        <Link
          href="/settings"
          className="inline-flex items-center gap-1.5 text-sm text-zinc-500 transition hover:text-zinc-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Settings
        </Link>
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
