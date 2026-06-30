"use client";

import { useIntegrations } from "@/context/IntegrationsContext";
import { INTEGRATION_CATALOG } from "@/lib/integrations";

import { GlobalSyncBanner } from "./GlobalSyncBanner";
import { IntegrationCard } from "./IntegrationCard";
import {
  IntegrationConfigDrawer,
  useSelectedIntegration,
} from "./IntegrationConfigDrawer";

interface IntegrationsDirectoryProps {
  showSyncBanner?: boolean;
  className?: string;
}

export function IntegrationsDirectory({
  showSyncBanner = true,
  className = "",
}: IntegrationsDirectoryProps) {
  const { getStatus } = useIntegrations();
  const { selectedApp, open, close } = useSelectedIntegration();

  return (
    <div className={`space-y-8 ${className}`}>
      {showSyncBanner && <GlobalSyncBanner />}

      <section>
        <div className="mb-4">
          <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
            App directory
          </h2>
          <p className="mt-1 text-sm text-zinc-400">
            Connect engineering tools — credentials are shared across onboarding
            and settings.
          </p>
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
