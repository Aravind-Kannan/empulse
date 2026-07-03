"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Loader2, RefreshCw, Save, Users } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { useAuth } from "@/context/AuthContext";
import {
  fetchIdentityReconciliation,
  fetchProviderMembersBundle,
  saveIdentityMappings,
  syncIdentityMappings,
} from "@/lib/api";
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
  ProviderMember,
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

function guessMapping(
  employee: Pick<EmployeeIdentityRow, "name" | "email">,
  members: ProviderMember[],
): string | null {
  const email = employee.email.toLowerCase();
  for (const member of members) {
    if (member.email && member.email.toLowerCase() === email) {
      return member.id;
    }
  }
  const nameSlug = employee.name.toLowerCase().replace(/\s/g, "");
  for (const member of members) {
    const labelSlug = member.label.toLowerCase().replace(/[-.]/g, "");
    if (nameSlug && labelSlug.includes(nameSlug)) {
      return member.id;
    }
  }
  return null;
}

function memberLabel(
  members: ProviderMember[],
  memberId: string | null | undefined,
): string {
  if (!memberId) return "";
  const match = members.find((member) => member.id === memberId);
  if (!match) return memberId;
  return match.email ? `${match.label} (${match.email})` : match.label;
}

export function IdentityMappingPage() {
  const { config } = useIntegrations();
  const { activeTenant } = useAuth();
  const [data, setData] = useState<IdentityReconciliationResponse | null>(null);
  const [rows, setRows] = useState<EmployeeIdentityRow[]>([]);
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(true);
  const [isLoadingMembers, setIsLoadingMembers] = useState(false);
  const [membersLoadComplete, setMembersLoadComplete] = useState(false);
  const [membersLoadSummary, setMembersLoadSummary] = useState<
    Partial<Record<IdentityProvider, number>>
  >({});
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [importRoster, setImportRoster] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const membersRequestId = useRef(0);

  const connectedProviders = useMemo(() => {
    return INTEGRATION_CATALOG.filter((app) =>
      isIntegrationConnected(app.id, config),
    ).map((app) => PROVIDER_BY_INTEGRATION[app.id]);
  }, [config]);

  const applyMemberGuesses = useCallback(
    (
      currentRows: EmployeeIdentityRow[],
      provider: IdentityProvider,
      members: ProviderMember[],
    ) => {
      if (members.length === 0) return currentRows;
      return currentRows.map((row) => {
        if (row.mappings[provider]) {
          return row;
        }
        const guessed = guessMapping(row, members);
        if (!guessed) {
          return row;
        }
        return {
          ...row,
          mappings: { ...row.mappings, [provider]: guessed },
        };
      });
    },
    [],
  );

  const loadProviderMembers = useCallback(
    async (providers: IdentityProvider[]) => {
      if (providers.length === 0) {
        setIsLoadingMembers(false);
        return;
      }

      const requestId = membersRequestId.current + 1;
      membersRequestId.current = requestId;
      setIsLoadingMembers(true);
      setMembersLoadComplete(false);
      setMembersLoadSummary({});

      try {
        const bundle = await fetchProviderMembersBundle(providers);
        if (membersRequestId.current !== requestId) {
          return;
        }

        const summary: Partial<Record<IdentityProvider, number>> = {};
        for (const provider of providers) {
          summary[provider] = bundle.provider_members[provider]?.length ?? 0;
        }

        setData((prev) =>
          prev
            ? {
                ...prev,
                provider_members: {
                  ...prev.provider_members,
                  ...bundle.provider_members,
                },
                provider_warnings: {
                  ...prev.provider_warnings,
                  ...bundle.provider_warnings,
                },
              }
            : prev,
        );

        setRows((prev) => {
          let next = prev;
          for (const provider of providers) {
            const members = bundle.provider_members[provider] ?? [];
            next = applyMemberGuesses(next, provider, members);
          }
          return next;
        });
        setMembersLoadSummary(summary);
        setMembersLoadComplete(true);
      } catch (err) {
        if (membersRequestId.current === requestId) {
          setMembersLoadComplete(false);
          setMembersLoadSummary({});
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load provider member directories",
          );
        }
      } finally {
        if (membersRequestId.current === requestId) {
          setIsLoadingMembers(false);
        }
      }
    },
    [applyMemberGuesses],
  );

  const loadReconciliation = useCallback(
    async (options?: { background?: boolean }) => {
      const background = options?.background ?? false;
      if (!background) {
        setIsLoadingEmployees(true);
      }
      setError(null);

      if (connectedProviders.length === 0) {
        setData(null);
        setRows([]);
        setIsLoadingEmployees(false);
        setIsLoadingMembers(false);
        setMembersLoadComplete(false);
        setMembersLoadSummary({});
        return;
      }

      try {
        const response = await fetchIdentityReconciliation(connectedProviders, {
          includeLiveMembers: false,
        });
        setData(response);
        setRows(response.employees);
        void loadProviderMembers(connectedProviders);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load mappings");
      } finally {
        if (!background) {
          setIsLoadingEmployees(false);
        }
      }
    },
    [connectedProviders, loadProviderMembers],
  );

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

  async function handleSync() {
    if (connectedProviders.length === 0) return;

    setIsSyncing(true);
    setError(null);
    setSyncMessage(null);
    setSavedMessage(null);

    try {
      const result = await syncIdentityMappings({
        providers: connectedProviders,
        import_roster: importRoster,
        company: activeTenant?.companyName ?? null,
      });
      const rosterNote =
        result.roster && result.roster.employees_added + result.roster.employees_updated > 0
          ? ` Roster: +${result.roster.employees_added} added, ${result.roster.employees_updated} updated.`
          : "";
      const providerNote = result.providers
        .map(
          (row) =>
            `${row.provider}: ${row.members_fetched} members, ${row.mappings_created} mapped`,
        )
        .join("; ");
      setSyncMessage(
        `Synced identities — ${result.total_mappings_created} new mapping(s). ${providerNote}.${rosterNote}`,
      );
      await loadReconciliation({ background: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Identity sync failed");
    } finally {
      setIsSyncing(false);
    }
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
      await loadReconciliation({ background: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  const loadingMembersLabel = connectedProviders
    .map((provider) => PROVIDER_LABELS[provider])
    .join(", ");

  const membersLoadedLabel = connectedProviders
    .map((provider) => {
      const count = membersLoadSummary[provider];
      if (count === undefined) {
        return PROVIDER_LABELS[provider];
      }
      return `${PROVIDER_LABELS[provider]} (${count})`;
    })
    .join(", ");

  const showWorkspace =
    !isLoadingEmployees && data && connectedProviders.length > 0;

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
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-zinc-400">
              <input
                type="checkbox"
                checked={importRoster}
                onChange={(e) => setImportRoster(e.target.checked)}
                className="rounded border-zinc-600 bg-zinc-950"
              />
              Also import employee roster
            </label>
            <button
              type="button"
              onClick={() => void handleSync()}
              disabled={
                isSyncing || isLoadingEmployees || connectedProviders.length === 0
              }
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSyncing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Sync from integrations
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={
                isSaving || isLoadingEmployees || connectedProviders.length === 0
              }
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

      {isLoadingMembers && connectedProviders.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-200">
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
          <div>
            <p className="font-medium">Pulling member directories from integrations</p>
            <p className="mt-1 text-sky-200/80">
              Loading {loadingMembersLabel} accounts to populate dropdown options.
              Saved mappings stay visible while this finishes.
            </p>
          </div>
        </div>
      )}

      {!isLoadingMembers && membersLoadComplete && connectedProviders.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
          <div>
            <p className="font-medium text-emerald-100">
              Member directories loaded — dropdowns ready
            </p>
            <p className="mt-1 text-emerald-200/80">
              Pulled from {membersLoadedLabel}. Review auto-suggested mappings and
              save any changes.
            </p>
          </div>
        </div>
      )}

      {syncMessage && (
        <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 px-4 py-3 text-sm text-sky-200">
          {syncMessage}
        </div>
      )}

      {savedMessage && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {savedMessage}
        </div>
      )}

      {isLoadingEmployees ? (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading employee roster and saved mappings…
        </div>
      ) : showWorkspace ? (
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/60">
              <tr>
                <th className="px-4 py-3 font-medium text-zinc-300">Employee</th>
                <th className="px-4 py-3 font-medium text-zinc-300">Email</th>
                {data.connected_providers.map((provider) => {
                  const memberCount = data.provider_members[provider]?.length ?? 0;
                  const membersReady = memberCount > 0 || !isLoadingMembers;
                  return (
                    <th
                      key={provider}
                      className="px-4 py-3 font-medium text-zinc-300"
                    >
                      <span className="inline-flex items-center gap-2">
                        {PROVIDER_LABELS[provider]}
                        {isLoadingMembers && (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                        )}
                        {!isLoadingMembers && membersLoadComplete && (
                          <span className="inline-flex items-center gap-1 text-xs font-normal text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {memberCount}
                          </span>
                        )}
                      </span>
                    </th>
                  );
                })}
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
                    const selectedLabel = memberLabel(members, selected);

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
                          disabled={isLoadingMembers && !selected}
                          className="w-full min-w-[10rem] rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100 outline-none focus:border-zinc-500 disabled:cursor-wait disabled:opacity-70"
                        >
                          <option value="">
                            {isLoadingMembers ? "Loading members…" : "Unmapped"}
                          </option>
                          {selected && !members.some((member) => member.id === selected) && (
                            <option value={selected}>{selectedLabel || selected}</option>
                          )}
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

      {showWorkspace && (
        <p className="text-xs text-zinc-500">
          Employee rows load from your org chart first. Provider member lists
          fill in shortly after from connected integrations. Use Sync from
          integrations to refresh directories (including GitHub repo
          contributors) and auto-map by email. Check &quot;Also import employee
          roster&quot; to merge new people into your org chart. Review and save
          manual overrides before re-syncing Cognee.
        </p>
      )}
    </div>
  );
}
