"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, Loader2, Save, Sparkles } from "lucide-react";

import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useIntegrations } from "@/context/IntegrationsContext";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
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
import {
  formatProviderMemberOption,
  memberLabelForProvider,
} from "@/lib/identity-member-label";

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

function rowsFingerprint(rows: EmployeeIdentityRow[]): string {
  return JSON.stringify(
    rows.map((row) => ({
      id: row.employee_id,
      mappings: row.mappings,
    })),
  );
}

interface IdentityMappingPanelProps {
  focusEmployeeId?: string | null;
  onDirtyChange?: (dirty: boolean) => void;
  integrationsHref?: string;
  /** Onboarding uses OrgWorkspace "Re-import from sources" instead. */
  hideRosterReimport?: boolean;
}

export function IdentityMappingPanel({
  focusEmployeeId = null,
  onDirtyChange,
  integrationsHref = "/settings/integrations",
  hideRosterReimport = false,
}: IdentityMappingPanelProps) {
  const { config } = useIntegrations();
  const { activeTenant } = useAuth();
  const { pushToast } = useToast();
  const [data, setData] = useState<IdentityReconciliationResponse | null>(null);
  const [rows, setRows] = useState<EmployeeIdentityRow[]>([]);
  const [providerMembers, setProviderMembers] = useState<
    Partial<Record<IdentityProvider, ProviderMember[]>>
  >({});
  const [providerWarnings, setProviderWarnings] = useState<
    Partial<Record<IdentityProvider, string>>
  >({});
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
  const [error, setError] = useState<string | null>(null);
  const [reimportConfirmOpen, setReimportConfirmOpen] = useState(false);
  const savedRowsSnapshot = useRef("");
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
        const warning = bundle.provider_warnings?.[provider];
        setProviderMembers((prev) => ({ ...prev, [provider]: members }));
        if (warning) {
          setProviderWarnings((prev) => ({ ...prev, [provider]: warning }));
        }
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
    [],
  );

  const loadReconciliation = useCallback(async () => {
    setIsLoadingEmployees(true);
    setError(null);
    loadedProvidersRef.current = new Set();
    loadingProvidersRef.current = new Set();
    setLoadedProviders(new Set());
    setLoadingProviders(new Set());
    setProviderMemberCounts({});
    setProviderMembers({});
    setProviderWarnings({});

    if (connectedProviders.length === 0) {
      setData(null);
      setRows([]);
      savedRowsSnapshot.current = "";
      setIsLoadingEmployees(false);
      return;
    }

    try {
      const response = await fetchIdentityReconciliation(connectedProviders, {
        includeLiveMembers: false,
      });
      setData(response);
      setRows(response.employees);
      savedRowsSnapshot.current = rowsFingerprint(response.employees);
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
    if (isLoadingEmployees || connectedProviders.length === 0) return;
    void Promise.all(
      connectedProviders.map((provider) => loadProviderMembers(provider)),
    );
  }, [connectedProviders, isLoadingEmployees, loadProviderMembers]);

  const hasUnsavedChanges =
    rows.length > 0 && savedRowsSnapshot.current !== rowsFingerprint(rows);

  useEffect(() => {
    onDirtyChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onDirtyChange]);

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
  }

  async function runReimportRoster() {
    if (connectedProviders.length === 0) return;

    setIsSyncing(true);
    setError(null);

    try {
      const result = await syncIdentityMappings({
        providers: connectedProviders,
        import_roster: true,
        replace_roster: true,
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
      pushToast(
        `Roster re-imported — ${result.total_mappings_created} new mapping(s). ${providerNote}.${rosterNote}`,
        "success",
      );
      setLoadedProviders(new Set());
      loadedProvidersRef.current = new Set();
      setProviderMemberCounts({});
      setProviderMembers({});
      setProviderWarnings({});
      await loadReconciliation();
      void Promise.all(
        connectedProviders.map((provider) => loadProviderMembers(provider)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Roster re-import failed");
    } finally {
      setIsSyncing(false);
    }
  }

  async function handleSync() {
    if (connectedProviders.length === 0) return;

    setIsSyncing(true);
    setError(null);

    try {
      const result = await syncIdentityMappings({
        providers: connectedProviders,
        import_roster: false,
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
      pushToast(
        `Auto-mapped ${result.total_mappings_created} identity link(s). ${providerNote}.${rosterNote}`,
        result.total_mappings_created > 0 ? "success" : "info",
      );
      setLoadedProviders(new Set());
      loadedProvidersRef.current = new Set();
      loadingProvidersRef.current = new Set();
      setLoadingProviders(new Set());
      setProviderMemberCounts({});
      setProviderMembers({});
      setProviderWarnings({});
      await loadReconciliation();
      void Promise.all(
        connectedProviders.map((provider) => loadProviderMembers(provider)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Identity sync failed");
    } finally {
      setIsSyncing(false);
    }
  }

  function membersForProvider(provider: IdentityProvider): ProviderMember[] {
    return providerMembers[provider] ?? data?.provider_members[provider] ?? [];
  }

  async function handleSave() {
    if (!data) return;

    setIsSaving(true);
    setError(null);

    const mappings: EmployeeIdentityMapping[] = [];
    for (const row of rows) {
      for (const provider of data.connected_providers) {
        const value = row.mappings[provider];
        if (value) {
          const members = membersForProvider(provider);
          const label = memberLabelForProvider(members, value, provider);
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
      savedRowsSnapshot.current = rowsFingerprint(rows);
      onDirtyChange?.(false);
      pushToast("Identity mappings saved.", "success");
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
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => void handleSync()}
            disabled={
              isSyncing || isLoadingEmployees || connectedProviders.length === 0
            }
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-100 transition hover:border-zinc-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSyncing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Auto-map identities
          </button>
          {hideRosterReimport ? null : (
            <button
              type="button"
              onClick={() => setReimportConfirmOpen(true)}
              disabled={
                isSyncing || isLoadingEmployees || connectedProviders.length === 0
              }
              className="inline-flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-100 transition hover:bg-amber-500/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Re-import roster
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={
              isSaving ||
              isLoadingEmployees ||
              connectedProviders.length === 0 ||
              !hasUnsavedChanges
            }
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-3 py-1.5 text-xs font-medium text-slate-950 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            Save mappings
          </button>
      </div>

      {connectedProviders.length === 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          No integrations connected yet. Connect apps in{" "}
          <Link href={integrationsHref} className="underline">
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

      {Object.keys(providerWarnings).length > 0
        ? Object.entries(providerWarnings).map(([provider, warning]) => (
            <div
              key={provider}
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
            >
              <span className="font-medium capitalize">{provider}:</span> {warning}
            </div>
          ))
        : data?.provider_warnings
          ? Object.entries(data.provider_warnings).map(([provider, warning]) => (
              <div
                key={provider}
                className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200"
              >
                <span className="font-medium capitalize">{provider}:</span>{" "}
                {warning}
              </div>
            ))
          : null}

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
                    const members = membersForProvider(provider);
                    const selected = row.mappings[provider] ?? "";
                    const selectedLabel = memberLabelForProvider(
                      members,
                      selected,
                      provider,
                    );
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
                              {formatProviderMemberOption(member, provider)}
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

      {hideRosterReimport ? null : (
        <ConfirmDialog
          open={reimportConfirmOpen}
          title="Re-import employee roster?"
          description="This pulls people from connected integrations and may add or update roster entries. Existing identity mappings are kept unless people are removed."
          confirmLabel="Re-import roster"
          cancelLabel="Cancel"
          onConfirm={() => {
            setReimportConfirmOpen(false);
            void runReimportRoster();
          }}
          onCancel={() => setReimportConfirmOpen(false)}
        />
      )}
    </div>
  );
}
