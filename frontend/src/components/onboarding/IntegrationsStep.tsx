"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Loader2, Plug } from "lucide-react";

import { IntegrationsDirectory } from "@/components/integrations/IntegrationsDirectory";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import { useOnboarding } from "@/context/OnboardingContext";
import { fetchEmployeeMasterData } from "@/lib/api";
import {
  getConnectedMemberImportSources,
  hasMemberImportSourceConnected,
} from "@/lib/integrations";

export function IntegrationsStep() {
  const router = useRouter();
  const { session, activeTenant } = useAuth();
  const { config } = useIntegrations();
  const { applyMasterData } = useOnboarding();
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const importReady = hasMemberImportSourceConnected(config);
  const connectedSources = getConnectedMemberImportSources(config);

  async function handleContinue() {
    setError(null);

    if (!importReady) {
      setError(
        "Connect and verify at least one integration (Slack, Notion, or GitHub) to import members.",
      );
      return;
    }

    setIsFetching(true);
    try {
      const company =
        activeTenant?.companyName ?? session?.company ?? "My Company";
      const master = await fetchEmployeeMasterData(
        connectedSources,
        company,
        config,
      );
      applyMasterData(master, company);
      router.push("/onboarding/org-setup");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to import members",
      );
    } finally {
      setIsFetching(false);
    }
  }

  return (
    <OnboardingShell currentStep={1} wide>
      <div className="mb-8 space-y-2">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900">
            <Plug className="h-5 w-5 text-zinc-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">
              Connect your data sources
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">
              Connect any integration below. We pull reporting lines from Slack
              (manager profile fields) and Notion people databases when
              available; otherwise members import as a flat roster you can
              organize on the next step.
            </p>
          </div>
        </div>

        {!importReady && (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            Connect and save at least one integration to import your member
            roster — Slack, Notion, or GitHub org.
          </p>
        )}
      </div>

      <IntegrationsDirectory showSyncBanner={false} />

      {error && (
        <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-8 flex flex-col gap-3 border-t border-zinc-800 pt-8 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={() => void handleContinue()}
          disabled={isFetching || !importReady}
          className="flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-6 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isFetching ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Importing members from{" "}
              {connectedSources
                .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
                .join(", ")}
              …
            </>
          ) : (
            "Import members & continue"
          )}
        </button>
      </div>
    </OnboardingShell>
  );
}
