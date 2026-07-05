"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { OrgWorkspace } from "@/components/org-workspace/OrgWorkspace";
import {
  MemberImportProgress,
  type MemberImportStep,
} from "@/components/onboarding/MemberImportProgress";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import { useOnboarding } from "@/context/OnboardingContext";
import { fetchOrgChart, ingestOrgChart, syncIdentityMappings } from "@/lib/api";
import { EMPTY_ORG_CHART } from "@/lib/acme-org";
import {
  getConnectedMemberImportSources,
  hasMemberImportSourceConnected,
  INTEGRATION_CATALOG,
  type IntegrationId,
} from "@/lib/integrations";
import type { Assignment, Employee } from "@/lib/types";
import { useWorkspace } from "@/context/WorkspaceContext";

function buildImportSteps(providers: IntegrationId[]): MemberImportStep[] {
  return [
    ...providers.map((id) => ({ id, status: "pending" as const })),
    { id: "hierarchy" as const, status: "pending" as const },
    { id: "identity" as const, status: "pending" as const },
  ];
}

function providerDetail(
  provider: IntegrationId,
  membersFetched: number,
  mappingsCreated: number,
  warning: string | null,
  rosterWarning: string | null,
): string {
  const parts: string[] = [];
  if (membersFetched > 0) {
    parts.push(
      `${membersFetched} identit${membersFetched === 1 ? "y" : "ies"} discovered`,
    );
  }
  if (mappingsCreated > 0) {
    parts.push(
      `${mappingsCreated} auto-mapped`,
    );
  }
  if (parts.length > 0) {
    const summary = parts.join(" · ");
    return rosterWarning ? `${summary} — ${rosterWarning}` : summary;
  }
  if (warning) return warning;
  if (rosterWarning) return rosterWarning;
  return `No new members found from ${provider}`;
}

function sourceLabels(providers: IntegrationId[]): string[] {
  return providers.map(
    (id) => INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id,
  );
}

function inferHierarchyMode(
  employees: { manager_id?: string | null }[],
): "flat" | "structured" {
  return employees.some((employee) => employee.manager_id) ? "structured" : "flat";
}

export function OnboardingOrgSetupPage() {
  const router = useRouter();
  const { session, activeTenant, completeOnboarding } = useAuth();
  const { config } = useIntegrations();
  const {
    orgChart,
    masterDataSources,
    hierarchyMode,
    reparentEmployee,
    assignTeamTag,
    setOrgChart,
    setImportMetadata,
    updateEmployee,
    addEmployee,
    removeEmployee,
    updateAssignments,
  } = useOnboarding();
  const { refreshOperationalState } = useWorkspace();
  const [isSaving, setIsSaving] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importSteps, setImportSteps] = useState<MemberImportStep[]>([]);
  const [savingLabel, setSavingLabel] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const importAbortRef = useRef(false);
  const importRunIdRef = useRef(0);
  const importSourcesKey = useMemo(
    () => getConnectedMemberImportSources(config).join(","),
    [config],
  );
  const connectedImportSources = useMemo(
    () =>
      importSourcesKey
        ? (importSourcesKey.split(",") as IntegrationId[])
        : [],
    [importSourcesKey],
  );

  const goToIntegrations = useCallback(() => {
    importAbortRef.current = true;
    importRunIdRef.current += 1;
    router.push("/onboarding");
  }, [router]);

  const runMemberImport = useCallback(async (options?: { replaceExisting?: boolean }) => {
    if (!hasMemberImportSourceConnected(config)) return;

    const replaceExisting = options?.replaceExisting ?? true;
    const runId = importRunIdRef.current + 1;
    importRunIdRef.current = runId;
    importAbortRef.current = false;

    const connected = connectedImportSources;
    const company =
      activeTenant?.companyName ?? session?.company ?? "My Company";

    setImportSteps(buildImportSteps(connected));
    setIsImporting(true);
    setError(null);
    if (replaceExisting) {
      setOrgChart({
        ...EMPTY_ORG_CHART,
        company,
      });
      setImportMetadata([], null);
    } else if (orgChart.employees.length > 0) {
      try {
        await ingestOrgChart(
          {
            ...orgChart,
            company: session?.company || orgChart.company || company,
          },
          { waitForCompletion: false },
        );
      } catch (err) {
        setIsImporting(false);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to save your edits before re-import",
        );
        return;
      }
    }

    const isStale = () =>
      importAbortRef.current || importRunIdRef.current !== runId;

    try {
      for (const [providerIndex, provider] of connected.entries()) {
        if (isStale()) return;

        setImportSteps((prev) =>
          prev.map((step) =>
            step.id === provider ? { ...step, status: "active" } : step,
          ),
        );

        try {
          const result = await syncIdentityMappings({
            providers: [provider],
            import_roster: true,
            replace_roster: replaceExisting && providerIndex === 0,
            company,
          });
            const row = result.providers[0];
            const membersFetched = row?.members_fetched ?? 0;
            const status: MemberImportStep["status"] =
              row?.warning && membersFetched === 0 ? "error" : "done";

          if (isStale()) return;

          setImportSteps((prev) =>
            prev.map((step) =>
              step.id === provider
                ? {
                    ...step,
                    status,
                    detail: row
                      ? providerDetail(
                          provider,
                          row.members_fetched,
                          row.mappings_created,
                          row.warning,
                          row.roster_warning ?? null,
                        )
                      : "Import finished",
                  }
                : step,
            ),
          );
        } catch (err) {
          if (isStale()) return;
          setImportSteps((prev) =>
            prev.map((step) =>
              step.id === provider
                ? {
                    ...step,
                    status: "error",
                    detail:
                      err instanceof Error
                        ? err.message
                        : `Failed to import from ${provider}`,
                  }
                : step,
            ),
          );
        }
      }

      if (isStale()) return;

      setImportSteps((prev) =>
        prev.map((step) =>
          step.id === "hierarchy" ? { ...step, status: "active" } : step,
        ),
      );

      const chart = await fetchOrgChart();
      if (isStale()) return;

      setOrgChart(chart);
      const mode = inferHierarchyMode(chart.employees);
      setImportMetadata(sourceLabels(connected), mode);

      setImportSteps((prev) =>
        prev.map((step) =>
          step.id === "hierarchy"
            ? {
                ...step,
                status: "done",
                detail: `${chart.employees.length} people ready to review`,
              }
            : step,
        ),
      );

      setImportSteps((prev) =>
        prev.map((step) =>
          step.id === "identity" ? { ...step, status: "active" } : step,
        ),
      );

      try {
        const identityResult = await syncIdentityMappings({
          providers: connected,
          import_roster: false,
        });
        if (isStale()) return;

        const mapped = identityResult.providers.reduce(
          (total, row) => total + row.mappings_created,
          0,
        );
        setImportSteps((prev) =>
          prev.map((step) =>
            step.id === "identity"
              ? {
                  ...step,
                  status: "done",
                  detail:
                    mapped > 0
                      ? `${mapped} identit${mapped === 1 ? "y" : "ies"} auto-mapped`
                      : "Mappings ready to review",
                }
              : step,
          ),
        );
      } catch (err) {
        if (isStale()) return;
        setImportSteps((prev) =>
          prev.map((step) =>
            step.id === "identity"
              ? {
                  ...step,
                  status: "error",
                  detail:
                    err instanceof Error
                      ? err.message
                      : "Identity mapping step failed",
                }
              : step,
          ),
        );
      }

      await new Promise((resolve) => window.setTimeout(resolve, 400));
    } catch (err) {
      if (isStale()) return;
      setImportSteps((prev) =>
        prev.map((step) =>
          step.status === "active"
            ? {
                ...step,
                status: "error",
                detail:
                  err instanceof Error ? err.message : "Import step failed",
              }
            : step,
        ),
      );
      setError(
        err instanceof Error
          ? err.message
          : "Failed to import org hierarchy automatically",
      );
    } finally {
      if (!isStale()) {
        setIsImporting(false);
      }
    }
  }, [
    activeTenant?.companyName,
    connectedImportSources,
    orgChart,
    session?.company,
    setImportMetadata,
    setOrgChart,
  ]);

  useEffect(() => {
    if (!hasMemberImportSourceConnected(config)) {
      router.replace("/onboarding");
      return;
    }

    void runMemberImport();

    return () => {
      importAbortRef.current = true;
      importRunIdRef.current += 1;
    };
    // Re-import on each step-2 visit and when connected sources change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importSourcesKey]);

  async function handleUpdateEmployee(
    employee: Employee,
    assignments: Assignment[],
  ) {
    updateEmployee(employee);
    updateAssignments(assignments, employee.id);
  }

  async function handleAddEmployee(employee: Employee) {
    addEmployee(employee);
  }

  async function handleDeleteEmployee(employeeId: string) {
    removeEmployee(employeeId);
  }

  async function handleSkip() {
    setSkipDialogOpen(false);
    setIsSkipping(true);
    setError(null);
    try {
      await completeOnboarding();
      await refreshOperationalState();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to skip setup");
      setIsSkipping(false);
    }
  }

  async function handleSave() {
    setIsSaving(true);
    setSavingLabel("Saving org chart…");
    setError(null);

    const payload = {
      ...orgChart,
      company: session?.company || orgChart.company,
    };

    try {
      void ingestOrgChart(payload, {
        onStatus: (status) => {
          if (status.status === "queued" || status.status === "running") {
            setSavingLabel("Building knowledge graph…");
          }
        },
      }).catch(() => {
        // Non-blocking — user can sync from dashboard if ingest fails.
      });
      await completeOnboarding();
      await refreshOperationalState();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete setup");
      setIsSaving(false);
    }
  }

  if (isImporting) {
    return (
      <OnboardingShell
        currentStep={2}
        wide
        onStepClick={(step) => {
          if (step === 1) goToIntegrations();
        }}
      >
        <MemberImportProgress
          steps={importSteps}
          subtitle="Pulling people from each connected source, building your org chart, and auto-mapping identities."
        />

        {error ? (
          <div className="mx-auto mt-6 max-w-md rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell
      currentStep={2}
      wide
      onStepClick={(step) => {
        if (step === 1) goToIntegrations();
      }}
    >
      <OrgWorkspace
        mode="onboarding"
        orgChart={orgChart}
        masterDataSources={masterDataSources}
        hierarchyMode={hierarchyMode}
        isSaving={isSaving}
        isSkipping={isSkipping}
        savingLabel={savingLabel}
        error={error}
        onReparent={reparentEmployee}
        onAssignTeam={assignTeamTag}
        onReplaceOrgChart={setOrgChart}
        onUpdateEmployee={handleUpdateEmployee}
        onDeleteEmployee={handleDeleteEmployee}
        onAddEmployee={handleAddEmployee}
        onReimportFromSources={({ replaceExisting }) =>
          void runMemberImport({ replaceExisting })
        }
        isReimporting={isImporting}
        onBack={goToIntegrations}
        onSkip={() => setSkipDialogOpen(true)}
        onSave={handleSave}
      />

      <ConfirmDialog
        open={skipDialogOpen}
        title="Skip org chart for now?"
        description="Imported people stay in your workspace. Finish reviewing and saving later from Organization Hub in Settings."
        confirmLabel="Go to dashboard"
        cancelLabel="Keep editing"
        onConfirm={() => void handleSkip()}
        onCancel={() => setSkipDialogOpen(false)}
      />
    </OnboardingShell>
  );
}
