"use client";

import Link from "next/link";
import { ArrowLeft, Plug } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { INTEGRATION_CATALOG } from "@/lib/integrations";

import { GlobalSyncBanner } from "./GlobalSyncBanner";
import { IntegrationCard } from "./IntegrationCard";
import {
  IntegrationConfigDrawer,
  useSelectedIntegration,
} from "./IntegrationConfigDrawer";

export function IntegrationsPage() {
  const { getStatus } = useIntegrations();
  const { selectedApp, open, close } = useSelectedIntegration();

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-8">
      <header className="space-y-4">
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
              Connect engineering tools and sync their metadata into your Cognee
              knowledge graph. Manage credentials and trigger ingestion from one
              place.
            </p>
          </div>
        </div>
      </header>

      <GlobalSyncBanner />

      <section>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
              App directory
            </h2>
            <p className="mt-1 text-sm text-zinc-400">
              Browse available connectors for your workspace.
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {INTEGRATION_CATALOG.map((app) => (
            <IntegrationCard
              key={app.id}
              app={app}
              status={getStatus(app.id)}
              onAction={() => open(app.id)}
            />
          ))}
        </div>
      </section>

      {selectedApp && (
        <IntegrationConfigDrawer app={selectedApp} onClose={close} />
      )}
    </div>
  );
}
