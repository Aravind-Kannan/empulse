"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { OrgWorkspace } from "@/components/org-workspace/OrgWorkspace";
import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import { useOnboarding } from "@/context/OnboardingContext";
import { ingestOrgChart } from "@/lib/api";
import { hasMemberImportSourceConnected } from "@/lib/integrations";
import type { Assignment, Employee } from "@/lib/types";
import { useWorkspace } from "@/context/WorkspaceContext";

export function OnboardingOrgSetupPage() {
  const router = useRouter();
  const { session } = useAuth();
  const { config } = useIntegrations();
  const {
    orgChart,
    masterDataSources,
    hierarchyMode,
    reparentEmployee,
    assignTeamTag,
    setOrgChart,
    updateEmployee,
    addEmployee,
    updateAssignments,
  } = useOnboarding();
  const { refreshOperationalState } = useWorkspace();
  const [isSaving, setIsSaving] = useState(false);
  const [savingLabel, setSavingLabel] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasMemberImportSourceConnected(config)) {
      router.replace("/onboarding");
    }
  }, [config, router]);

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

  async function handleSave() {
    setIsSaving(true);
    setSavingLabel("Saving org chart…");
    setError(null);

    const payload = {
      ...orgChart,
      company: session?.company || orgChart.company,
    };

    try {
      await ingestOrgChart(payload, {
        onStatus: (status) => {
          if (status.status === "queued" || status.status === "running") {
            setSavingLabel("Building knowledge graph…");
          }
        },
      });
      await refreshOperationalState();
      router.push("/onboarding/sync");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
      setIsSaving(false);
    }
  }

  return (
    <OnboardingShell currentStep={2} wide>
      <OrgWorkspace
        mode="onboarding"
        orgChart={orgChart}
        masterDataSources={masterDataSources}
        hierarchyMode={hierarchyMode}
        isSaving={isSaving}
        savingLabel={savingLabel}
        error={error}
        onReparent={reparentEmployee}
        onAssignTeam={assignTeamTag}
        onReplaceOrgChart={setOrgChart}
        onUpdateEmployee={handleUpdateEmployee}
        onAddEmployee={handleAddEmployee}
        onSave={handleSave}
      />
    </OnboardingShell>
  );
}
