"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Plug } from "lucide-react";

import { IntegrationConfigDrawer } from "@/components/integrations/IntegrationConfigDrawer";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  IntegrationPickerCard,
  type IntegrationPickerStatus,
} from "@/components/integrations/IntegrationPickerCard";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import { saveIntegrationConfigOnly } from "@/lib/api";
import {
  getConnectedIntegrationIds,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  isIntegrationDraft,
  type IntegrationConfigMap,
  type IntegrationId,
} from "@/lib/integrations";

function pickerStatus(
  id: IntegrationId,
  config: IntegrationConfigMap,
): IntegrationPickerStatus {
  if (isIntegrationConnected(id, config)) return "ready";
  if (isIntegrationDraft(id, config)) return "draft";
  return "not_connected";
}

function SkipSetupDialogBody({ connectedCount }: { connectedCount: number }) {
  if (connectedCount > 0) {
    const sourceLabel = `${connectedCount} connected source${connectedCount === 1 ? "" : "s"}`;
    return (
      <div className="space-y-3">
        <p>
          You can finish org chart and sync later. If you go to the dashboard now:
        </p>
        <ul className="space-y-2.5">
          <li className="flex gap-2.5">
            <span className="mt-0.5 shrink-0 text-emerald-400/90">✓</span>
            <span>
              <span className="font-medium text-zinc-300">Credentials saved</span>
              {" — "}
              {sourceLabel} stay connected. Sync does not start until you trigger
              it from the dashboard.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="mt-0.5 shrink-0 text-amber-400/90">→</span>
            <span>
              <span className="font-medium text-zinc-300">Org chart skipped</span>
              {" — "}
              Import people later from Organization Hub under Settings.
            </span>
          </li>
          <li className="flex gap-2.5">
            <span className="mt-0.5 shrink-0 text-zinc-500">○</span>
            <span>
              <span className="font-medium text-zinc-300">Analytics preview only</span>
              {" — "}
              ERA, KRA, Investigation, and Exit stay blurred until sync completes.
            </span>
          </li>
        </ul>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p>
        No integrations connected yet. You can still open the dashboard and connect
        sources when ready.
      </p>
      <ul className="space-y-2.5">
        <li className="flex gap-2.5">
          <span className="mt-0.5 shrink-0 text-zinc-500">○</span>
          <span>
            <span className="font-medium text-zinc-300">Empty workspace</span>
            {" — "}
            Dashboard shows a setup checklist until at least one source is verified.
          </span>
        </li>
        <li className="flex gap-2.5">
          <span className="mt-0.5 shrink-0 text-amber-400/90">→</span>
          <span>
            <span className="font-medium text-zinc-300">Org chart skipped</span>
            {" — "}
            Finish people setup later from Organization Hub.
          </span>
        </li>
        <li className="flex gap-2.5">
          <span className="mt-0.5 shrink-0 text-zinc-500">○</span>
          <span>
            <span className="font-medium text-zinc-300">Analytics preview only</span>
            {" — "}
            ERA, KRA, Investigation, and Exit stay blurred until you connect sources
            and run sync.
          </span>
        </li>
      </ul>
    </div>
  );
}

export function Step1Integrations() {
  const router = useRouter();
  const { completeOnboarding } = useAuth();
  const { config } = useIntegrations();
  const [selectedAppId, setSelectedAppId] = useState<IntegrationId | null>(null);
  const [highlightedAppId, setHighlightedAppId] = useState<IntegrationId | null>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connectedCount = getConnectedIntegrationIds(config).length;
  const selectedApp = useMemo(
    () => INTEGRATION_CATALOG.find((app) => app.id === selectedAppId) ?? null,
    [selectedAppId],
  );

  useEffect(() => {
    return () => {
      if (highlightTimerRef.current) {
        clearTimeout(highlightTimerRef.current);
      }
    };
  }, []);

  function flashSavedCard(appId: IntegrationId) {
    if (highlightTimerRef.current) {
      clearTimeout(highlightTimerRef.current);
    }
    setHighlightedAppId(appId);
    highlightTimerRef.current = setTimeout(() => {
      setHighlightedAppId(null);
      highlightTimerRef.current = null;
    }, 2500);
  }

  async function persistConnectedConfigs() {
    const connected = getConnectedIntegrationIds(config);
    for (const id of connected) {
      await saveIntegrationConfigOnly(id, config);
    }
  }

  async function handleContinue() {
    setError(null);
    if (connectedCount === 0) {
      setError(
        "Connect and verify at least one integration, or choose “Finish setup later”.",
      );
      return;
    }

    setIsSaving(true);
    try {
      await persistConnectedConfigs();
      router.push("/onboarding/org-setup");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save credentials");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSkipAll() {
    setSkipDialogOpen(false);
    setIsSkipping(true);
    setError(null);
    try {
      if (connectedCount > 0) {
        await persistConnectedConfigs();
      }
      await completeOnboarding();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to skip onboarding");
      setIsSkipping(false);
    }
  }

  function handleSaveComplete(appId: IntegrationId) {
    flashSavedCard(appId);
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
              Choose an app to configure credentials and sync scope. Data sync
              starts from your dashboard when you choose — not during onboarding.
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {INTEGRATION_CATALOG.map((app) => (
          <IntegrationPickerCard
            key={app.id}
            app={app}
            status={pickerStatus(app.id, config)}
            justSaved={highlightedAppId === app.id}
            onConfigure={() => {
              if (highlightTimerRef.current) {
                clearTimeout(highlightTimerRef.current);
                highlightTimerRef.current = null;
              }
              setHighlightedAppId(null);
              setSelectedAppId(app.id);
            }}
          />
        ))}
      </div>

      {selectedApp && (
        <IntegrationConfigDrawer
          app={selectedApp}
          connectMode="credentials-only"
          onClose={() => setSelectedAppId(null)}
          onSaveComplete={handleSaveComplete}
          banner={
            <p className="text-xs leading-relaxed text-sky-200/90">
              Sync scope is saved now; data sync runs from your dashboard when
              you choose.
            </p>
          }
        />
      )}

      {error && (
        <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-8 flex flex-col gap-4 border-t border-zinc-800 pt-8 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={() => setSkipDialogOpen(true)}
          disabled={isSaving || isSkipping}
          className="inline-flex items-center gap-2 text-sm text-zinc-500 transition hover:text-zinc-300 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSkipping && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {isSkipping ? "Opening dashboard…" : "Finish setup later"}
        </button>

        <button
          type="button"
          onClick={() => void handleContinue()}
          disabled={isSaving || isSkipping || connectedCount === 0}
          className="flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-6 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSaving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving credentials…
            </>
          ) : (
            "Save & continue"
          )}
        </button>
      </div>

      <ConfirmDialog
        open={skipDialogOpen}
        title={
          connectedCount > 0
            ? "Go to dashboard without org chart?"
            : "Open dashboard without integrations?"
        }
        description={<SkipSetupDialogBody connectedCount={connectedCount} />}
        confirmLabel="Go to dashboard"
        cancelLabel="Continue setup"
        wide
        onConfirm={() => void handleSkipAll()}
        onCancel={() => setSkipDialogOpen(false)}
      />
    </OnboardingShell>
  );
}
