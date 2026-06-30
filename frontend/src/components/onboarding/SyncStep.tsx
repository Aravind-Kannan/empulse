"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2, Network } from "lucide-react";

import { GlobalSyncBanner } from "@/components/integrations/GlobalSyncBanner";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import {
  getConnectedIntegrationIds,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
} from "@/lib/integrations";

export function SyncStep() {
  const router = useRouter();
  const { completeOnboarding } = useAuth();
  const { config, syncProgress, triggerGlobalSync } = useIntegrations();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncStarted, setSyncStarted] = useState(false);

  const connectedCount = getConnectedIntegrationIds(config).length;

  useEffect(() => {
    if (connectedCount === 0 || syncStarted) return;
    setSyncStarted(true);
    void triggerGlobalSync();
  }, [connectedCount, syncStarted, triggerGlobalSync]);

  async function handleFinish() {
    setFinishing(true);
    setError(null);
    try {
      await completeOnboarding();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete setup");
      setFinishing(false);
    }
  }

  return (
    <OnboardingShell currentStep={3} wide>
      <div className="mb-8 flex items-start gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
          <Network className="h-5 w-5 text-zinc-300" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">
            Sync your knowledge graph
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Ingest metadata from every connected source into your tenant&apos;s
            Cognee dataset. Workspaces unlock as each integration finishes
            syncing.
          </p>
        </div>
      </div>

      <GlobalSyncBanner />

      <section className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <h2 className="text-sm font-medium uppercase tracking-wide text-zinc-500">
          Workspace readiness
        </h2>
        <ul className="mt-4 space-y-2">
          {INTEGRATION_CATALOG.map((app) => {
            const connected = isIntegrationConnected(app.id, config);
            return (
              <li
                key={app.id}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-950/50 px-4 py-3 text-sm"
              >
                <span className="text-zinc-300">{app.name}</span>
                <span
                  className={
                    connected
                      ? "text-emerald-400"
                      : "text-zinc-600"
                  }
                >
                  {connected ? "Connected" : "Not connected"}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      {error && (
        <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-8 flex justify-end border-t border-zinc-800 pt-8">
        <button
          type="button"
          onClick={() => void handleFinish()}
          disabled={finishing || syncProgress.active}
          className="flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-6 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {finishing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Opening dashboard…
            </>
          ) : syncProgress.active ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Waiting for sync…
            </>
          ) : (
            "Enter dashboard"
          )}
        </button>
      </div>
    </OnboardingShell>
  );
}
