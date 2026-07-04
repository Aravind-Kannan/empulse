"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, RefreshCw, Save } from "lucide-react";

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

interface IdentityMappingPanelProps {
  focusEmployeeId?: string | null;
  /** When true, fetch all connected provider directories in the background. */
  preloadProviderMembers?: boolean;
  /** When false, panel stays mounted but hidden (for background preload). */
  visible?: boolean;
}

export function IdentityMappingPanel({
  focusEmployeeId = null,
  preloadProviderMembers = false,
  visible = true,
}: IdentityMappingPanelProps) {
  const { config } = useIntegrations();
  const { activeTenant } = useAuth();
  const [data, setData] = useState<IdentityReconciliationResponse | null>(null);
  const [rows, setRows] = useState<EmployeeIdentityRow[]>([]);
  const [isLoadingEmployees, setIsLoadingEmployees] = useState(true);
  const [loadedProviders, setLoadedProviders] = useState<Set<IdentityProvider>>(
    () => new Set(),
  );
  const [loadingProviders, setLoadingProviders] = useState<Set<IdentityProvider>>(
    () => new Set(),
  );
  const [providerMemberCounts, setProviderMemberCounts] = useState<
    Partial<Record<IdentityProvider, number>>
  >({});
  const [isSaving, setIsSaving] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [importRoster, setImportRoster] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const providerRequestIds = useRef<Partial<Record<IdentityProvider, number>>>(
    {},
  );
  const loadingProvidersRef = useRef<Set<IdentityProvider>>(new Set());
  const loadedProvidersRef = useRef<Set<IdentityProvider>>(new Set());
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

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
    async (provider: IdentityProvider) => {
      if (
        loadedProvidersRef.current.has(provider) ||
        loadingProvidersRef.current.has(provider)
      ) {
        return;
      }

      const requestId = (providerRequestIds.current[provider] ?? 0) + 1;
      providerRequestIds.current[provider] = requestId;
      loadingProvidersRef.current.add(provider);
      setLoadingProviders((prev) => new Set(prev).add(provider));

      try {
        const bundle = await fetchProviderMembersBundle([provider]);
        if (providerRequestIds.current[provider] !== requestId) {
          return;
        }

        const members = bundle.provider_members[provider] ?? [];
        setData((prev) =>
          prev
            ? {
                ...prev,
                provider_members: {
                  ...prev.provider_members,
                  [provider]: members,
                },
                provider_warnings: {
                  ...prev.provider_warnings,
                  ...(bundle.provider_warnings?.[provider]
                    ? { [provider]: bundle.provider_warnings[provider]! }
                    : {}),
                },
              }
            : prev,
        );
        setRows((prev) => applyMemberGuesses(prev, provider, members));
        setProviderMemberCounts((prev) => ({
          ...prev,
          [provider]: members.length,
        }));
        loadedProvidersRef.current.add(provider);
        setLoadedProviders(new Set(loadedProvidersRef.current));
      } catch (err) {
        if (providerRequestIds.current[provider] === requestId) {
          setError(
            err instanceof Error
              ? err.message
              : `Failed to load ${PROVIDER_LABELS[provider]} members`,
          );
        }
      } finally {
        if (providerRequestIds.current[provider] === requestId) {
          loadingProvidersRef.current.delete(provider);
          setLoadingProviders((prev) => {
            const next = new Set(prev);
            next.delete(provider);
            return next;
          });
        }
      }
    },
    [applyMemberGuesses],
  );

  const loadReconciliation = useCallback(async () => {
    setIsLoadingEmployees(true);
    setError(null);

    if (connectedProviders.length === 0) {
      setData(null);
      setRows([]);
      setIsLoadingEmployees(false);
      return;
    }

    try {
      const response = await fetchIdentityReconciliation(connectedProviders, {
        includeLiveMembers: false,
      });
      setData(response);
      setRows(response.employees);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mappings");
    } finally {
      setIsLoadingEmployees(false);
    }
  }, [connectedProviders]);

  useEffect(() => {
    void loadReconciliation();
  }, [loadReconciliation]);

  useEffect(() => {
    if (!preloadProviderMembers || connectedProviders.length === 0) {
      return;
    }
    void Promise.all(
      connectedProviders.map((provider) => loadProviderMembers(provider)),
    );
  }, [preloadProviderMembers, connectedProviders, loadProviderMembers]);

  useEffect(() => {
    if (!focusEmployeeId) return;
    const row = rowRefs.current[focusEmployeeId];
    if (row) {
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.add("bg-sky-500/10");
      const timer = window.setTimeout(() => {
        row.classList.remove("bg-sky-500/10");
      }, 2000);
      return () => window.clearTimeout(timer);
    }
  }, [focusEmployeeId, rows]);

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
      setLoadedProviders(new Set());
      loadedProvidersRef.current = new Set();
      setProviderMemberCounts({});
      await loadReconciliation();
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
          const members = data.provider_members[provider] ?? [];
          const label = memberLabel(members, value);
          mappings.push({
            employee_id: row.employee_id,
            provider,
            provider_username_or_id: value,
            provider_display_label: label || value,
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

  const showWorkspace =
    !isLoadingEmployees && data && connectedProviders.length > 0;

  return (
    <div className={visible ? "space-y-5" : "hidden"} aria-hidden={!visible}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-500">
          Saved mappings load from your workspace with stored display names. Provider
          directories preload in the background while you browse People.
        </p>
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
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-medium text-zinc-100 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSyncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Sync &amp; auto-map
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={
              isSaving || isLoadingEmployees || connectedProviders.length === 0
            }
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
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

      {connectedProviders.length === 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          No integrations connected yet. Connect apps in{" "}
          <Link href="/settings/integrations" className="underline">
            Integrations
          </Link>{" "}
          to map provider identities.
        </div>
      )}

      {error ? (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {data?.provider_warnings
        ? Object.entries(data.provider_warnings).map(([provider, warning]) => (
            <div
              key={provider}
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
            >
              <span className="font-medium capitalize">{provider}:</span> {warning}
            </div>
          ))
        : null}

      {syncMessage ? (
        <div className="rounded-xl border border-sky-500/40 bg-sky-500/10 px-4 py-3 text-sm text-sky-200">
          {syncMessage}
        </div>
      ) : null}

      {savedMessage ? (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {savedMessage}
        </div>
      ) : null}

      {isLoadingEmployees ? (
        <div className="flex items-center justify-center py-16 text-zinc-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading saved mappings…
        </div>
      ) : showWorkspace ? (
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/60">
              <tr>
                <th className="px-4 py-3 font-medium text-zinc-300">Employee</th>
                <th className="px-4 py-3 font-medium text-zinc-300">Email</th>
                {data.connected_providers.map((provider) => {
                  const isLoading = loadingProviders.has(provider);
                  const isLoaded = loadedProviders.has(provider);
                  const memberCount = providerMemberCounts[provider];
                  return (
                    <th
                      key={provider}
                      className="px-4 py-3 font-medium text-zinc-300"
                    >
                      <span className="inline-flex items-center gap-2">
                        {PROVIDER_LABELS[provider]}
                        {isLoading ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                        ) : null}
                        {isLoaded && memberCount !== undefined ? (
                          <span className="inline-flex items-center gap-1 text-xs font-normal text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            {memberCount}
                          </span>
                        ) : null}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.employee_id}
                  ref={(node) => {
                    rowRefs.current[row.employee_id] = node;
                  }}
                  className="border-b border-zinc-800/80 transition-colors"
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-zinc-100">{row.name}</p>
                    <p className="text-xs text-zinc-500">{row.role}</p>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{row.email}</td>
                  {data.connected_providers.map((provider) => {
                    const members = data.provider_members[provider] ?? [];
                    const selected = row.mappings[provider] ?? "";
                    const selectedLabel = memberLabel(members, selected);
                    const isLoading = loadingProviders.has(provider);
                    const isLoaded = loadedProviders.has(provider);

                    return (
                      <td key={provider} className="px-4 py-3">
                        <select
                          value={selected}
                          onFocus={() => void loadProviderMembers(provider)}
                          onChange={(e) =>
                            updateMapping(
                              row.employee_id,
                              provider,
                              e.target.value,
                            )
                          }
                          className="w-full min-w-[10rem] rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm text-zinc-100 outline-none focus:border-zinc-500"
                        >
                          <option value="">
                            {isLoading
                              ? `Loading ${PROVIDER_LABELS[provider]}…`
                              : isLoaded
                                ? "Unmapped"
                                : `Open to load ${PROVIDER_LABELS[provider]}`}
                          </option>
                          {selected &&
                          !members.some((member) => member.id === selected) ? (
                            <option value={selected}>
                              {selectedLabel || selected}
                            </option>
                          ) : null}
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
    </div>
  );
}
