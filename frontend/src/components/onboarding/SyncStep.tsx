"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Loader2, Network } from "lucide-react";

import { GlobalSyncBanner } from "@/components/integrations/GlobalSyncBanner";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import { getConnectedIntegrationIds } from "@/lib/integrations";

export function SyncStep() {
  const router = useRouter();
  const { completeOnboarding } = useAuth();
  const { config, syncProgress, triggerGlobalSync } = useIntegrations();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const syncStartedRef = useRef(false);

  const connectedCount = getConnectedIntegrationIds(config).length;

  useEffect(() => {
    if (connectedCount === 0 || syncStartedRef.current || syncProgress.active) return;
    syncStartedRef.current = true;
    void triggerGlobalSync();
  }, [connectedCount, syncProgress.active, triggerGlobalSync]);

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
            Pull PRs, source code, blame, docs, and tickets from connected apps
            into your tenant Cognee dataset. Start sync when ready — unchanged
            data is skipped automatically.
          </p>
        </div>
      </div>

      {connectedCount === 0 && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          No integrations connected yet. Go back to connect Slack, GitHub, Jira,
          or Notion — or skip to the dashboard and connect later.
        </div>
      )}

      <GlobalSyncBanner />

      {syncProgress.error && (
        <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          Sync failed: {syncProgress.error}
        </div>
      )}

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
