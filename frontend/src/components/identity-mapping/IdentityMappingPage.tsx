"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2, Save, Users } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { fetchIdentityReconciliation, saveIdentityMappings } from "@/lib/api";
import {
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  type IntegrationId,
} from "@/lib/integrations";
import type {
  EmployeeIdentityMapping,
  EmployeeIdentityRow,
  IdentityProvider,
  IdentityReconciliationResponse,
} from "@/lib/types";

const PROVIDER_LABELS: Record<IdentityProvider, string> = {
  github: "GitHub",
  jira: "Jira",
  slack: "Slack",
  notion: "Notion",
};

const PROVIDER_BY_INTEGRATION: Record<IntegrationId, IdentityProvider> = {
  slack: "slack",
  notion: "notion",
  github: "github",
  jira: "jira",
};

export function IdentityMappingPage() {
  const { config } = useIntegrations();
  const [data, setData] = useState<IdentityReconciliationResponse | null>(null);
  const [rows, setRows] = useState<EmployeeIdentityRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const connectedProviders = useMemo(() => {
    return INTEGRATION_CATALOG.filter((app) =>
      isIntegrationConnected(app.id, config),
    ).map((app) => PROVIDER_BY_INTEGRATION[app.id]);
  }, [config]);

  const loadReconciliation = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    if (connectedProviders.length === 0) {
      setData(null);
      setRows([]);
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetchIdentityReconciliation(connectedProviders);
      setData(response);
      setRows(response.employees);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mappings");
    } finally {
      setIsLoading(false);
    }
  }, [connectedProviders]);

  useEffect(() => {
    void loadReconciliation();
  }, [loadReconciliation]);

  function updateMapping(
    employeeId: string,
    provider: IdentityProvider,
    value: string,
  ) {
    setRows((prev) =>
      prev.map((row) =>
        row.employee_id === employeeId
          ? {
              ...row,
              mappings: { ...row.mappings, [provider]: value || null },
            }
          : row,
      ),
    );
    setSavedMessage(null);
  }

  async function handleSave() {
    if (!data) return;

    setIsSaving(true);
    setError(null);
    setSavedMessage(null);

    const mappings: EmployeeIdentityMapping[] = [];
    for (const row of rows) {
      for (const provider of data.connected_providers) {
        const value = row.mappings[provider];
        if (value) {
          mappings.push({
            employee_id: row.employee_id,
            provider,
            provider_username_or_id: value,
          });
        }
      }
    }

    try {
      await saveIdentityMappings(mappings);
      setSavedMessage("Identity mappings saved.");
      await loadReconciliation();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-8">
      <header className="space-y-4">
        <Link
          href="/settings"
          className="inline-flex items-center gap-2 text-sm text-zinc-500 transition hover:text-zinc-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Settings
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
              <Users className="h-5 w-5 text-zinc-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-zinc-100">
                Identity Mapping
              </h1>
              <p className="text-sm text-zinc-500">
                Link employee records to GitHub, Jira, Slack, and Notion
                identities so Cognee merges graph nodes accurately.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || isLoading || connectedProviders.length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save mappings
          </button>
        </div>
      </header>

      {connectedProviders.length === 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          No integrations connected yet. Connect apps in{" "}
          <Link href="/settings/integrations" className="underline">
            Settings → Integrations
          </Link>{" "}
          to load provider member lists for mapping.
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {data?.provider_warnings &&
        Object.entries(data.provider_warnings).map(([provider, warning]) => (
          <div
            key={provider}
            className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
          >
            <span className="font-medium capitalize">{provider}:</span> {warning}
          </div>
        ))}

      {savedMessage && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {savedMessage}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading reconciliation workspace…
        </div>
      ) : data && connectedProviders.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/60">
              <tr>
                <th className="px-4 py-3 font-medium text-zinc-300">Employee</th>
                <th className="px-4 py-3 font-medium text-zinc-300">Email</th>
                {data.connected_providers.map((provider) => (
                  <th
                    key={provider}
                    className="px-4 py-3 font-medium text-zinc-300"
                  >
                    {PROVIDER_LABELS[provider]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.employee_id} className="border-b border-zinc-800/80">
                  <td className="px-4 py-3">
                    <p className="font-medium text-zinc-100">{row.name}</p>
                    <p className="text-xs text-zinc-500">{row.role}</p>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{row.email}</td>
                  {data.connected_providers.map((provider) => {
                    const members = data.provider_members[provider] ?? [];
                    const selected = row.mappings[provider] ?? "";

                    return (
                      <td key={provider} className="px-4 py-3">
                        <select
                          value={selected}
                          onChange={(e) =>
                            updateMapping(
                              row.employee_id,
                              provider,
                              e.target.value,
                            )
                          }
                          className="w-full min-w-[10rem] rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100 outline-none focus:border-zinc-500"
                        >
                          <option value="">Unmapped</option>
                          {members.map((member) => (
                            <option key={member.id} value={member.id}>
                              {member.label}
                              {member.email ? ` (${member.email})` : ""}
                            </option>
                          ))}
                        </select>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {data && connectedProviders.length > 0 && (
        <p className="text-xs text-zinc-500">
          Suggested mappings are pre-filled by matching email addresses across
          connected providers. Review and save before syncing to Cognee.
        </p>
      )}
    </div>
  );
}
