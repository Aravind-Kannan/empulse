"use client";

import { useState } from "react";
import { Loader2, Unplug, X } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  saveGitHubIntegrationConfig,
  saveJiraIntegrationConfig,
  syncIntegrationSource,
} from "@/lib/api";
import {
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  type IntegrationDefinition,
  type IntegrationId,
} from "@/lib/integrations";

import { IntegrationLogo } from "./IntegrationLogos";

interface IntegrationConfigDrawerProps {
  app: IntegrationDefinition;
  onClose: () => void;
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm text-zinc-300">{label}</label>
      {hint && <p className="mb-2 text-xs text-zinc-500">{hint}</p>}
      {children}
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500";

export function IntegrationConfigDrawer({
  app,
  onClose,
}: IntegrationConfigDrawerProps) {
  const { config, updateConfig, connect, disconnect } = useIntegrations();
  const { refreshOperationalState } = useWorkspace();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const connected = isIntegrationConnected(app.id, config);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      if (app.id === "github") {
        await saveGitHubIntegrationConfig(config.github);
        await syncIntegrationSource("github");
      } else if (app.id === "jira") {
        await saveJiraIntegrationConfig(config.jira);
        await syncIntegrationSource("jira");
      } else {
        await connect(app.id);
      }
      await refreshOperationalState();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integration");
    } finally {
      setSaving(false);
    }
  }

  function renderFields() {
    switch (app.id) {
      case "slack":
        return (
          <>
            <Field label="Workspace URL" hint="e.g. https://acme.slack.com">
              <input
                type="url"
                value={config.slack.workspaceUrl}
                onChange={(e) =>
                  updateConfig("slack", { workspaceUrl: e.target.value })
                }
                placeholder="https://your-team.slack.com"
                className={inputClass}
              />
            </Field>
            <Field label="Bot token" hint="xoxb-… scoped for channels:read">
              <input
                type="password"
                value={config.slack.botToken}
                onChange={(e) =>
                  updateConfig("slack", { botToken: e.target.value })
                }
                placeholder="xoxb-..."
                className={inputClass}
              />
            </Field>
            <Field label="Channel IDs" hint="Comma-separated channel IDs to sync">
              <input
                type="text"
                value={config.slack.channelIds}
                onChange={(e) =>
                  updateConfig("slack", { channelIds: e.target.value })
                }
                placeholder="C0123ABC, C0456DEF"
                className={inputClass}
              />
            </Field>
          </>
        );

      case "notion":
        return (
          <>
            <Field
              label="Integration token"
              hint="Internal integration secret from Notion"
            >
              <input
                type="password"
                value={config.notion.integrationToken}
                onChange={(e) =>
                  updateConfig("notion", {
                    integrationToken: e.target.value,
                  })
                }
                placeholder="secret_..."
                className={inputClass}
              />
            </Field>
            <Field
              label="Database / page IDs"
              hint="Comma-separated IDs for runbooks and wikis"
            >
              <input
                type="text"
                value={config.notion.databaseIds}
                onChange={(e) =>
                  updateConfig("notion", { databaseIds: e.target.value })
                }
                placeholder="a1b2c3d4-..., e5f6g7h8-..."
                className={inputClass}
              />
            </Field>
          </>
        );

      case "github":
        return (
          <>
            <Field label="Repository URL" hint="HTTPS clone URL or github.com/org/repo">
              <input
                type="url"
                value={config.github.repositoryUrl}
                onChange={(e) =>
                  updateConfig("github", { repositoryUrl: e.target.value })
                }
                placeholder="https://github.com/acme/platform"
                className={inputClass}
              />
            </Field>
            <Field label="Branch targeting" hint="Default branch for graph extraction">
              <input
                type="text"
                value={config.github.branchTarget}
                onChange={(e) =>
                  updateConfig("github", { branchTarget: e.target.value })
                }
                placeholder="main"
                className={inputClass}
              />
            </Field>
            <Field
              label="Personal access token (PAT)"
              hint="Fine-grained or classic token with repo read scope"
            >
              <input
                type="password"
                value={config.github.personalAccessToken}
                onChange={(e) =>
                  updateConfig("github", {
                    personalAccessToken: e.target.value,
                  })
                }
                placeholder="ghp_..."
                className={inputClass}
              />
            </Field>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
              <p className="text-sm font-medium text-zinc-200">OAuth</p>
              <p className="mt-1 text-xs text-zinc-500">
                Or authorize via GitHub OAuth for managed token rotation.
              </p>
              <button
                type="button"
                onClick={() =>
                  updateConfig("github", { oauthConnected: true })
                }
                className={`mt-3 w-full rounded-lg border px-3 py-2 text-sm transition ${
                  config.github.oauthConnected
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                    : "border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                {config.github.oauthConnected
                  ? "OAuth authorized"
                  : "Connect with GitHub OAuth"}
              </button>
            </div>
          </>
        );

      case "jira":
        return (
          <>
            <Field
              label="Site domain / instance URL"
              hint="Your Atlassian cloud site"
            >
              <input
                type="url"
                value={config.jira.siteUrl}
                onChange={(e) =>
                  updateConfig("jira", { siteUrl: e.target.value })
                }
                placeholder="https://acme.atlassian.net"
                className={inputClass}
              />
            </Field>
            <Field
              label="Project keys"
              hint="Comma-separated keys, e.g. ENG, PLAT, OPS"
            >
              <input
                type="text"
                value={config.jira.projectKeys}
                onChange={(e) =>
                  updateConfig("jira", { projectKeys: e.target.value })
                }
                placeholder="ENG, PLAT"
                className={inputClass}
              />
            </Field>
            <Field
              label="API access token"
              hint="Atlassian API token paired with your account email"
            >
              <input
                type="password"
                value={config.jira.apiToken}
                onChange={(e) =>
                  updateConfig("jira", { apiToken: e.target.value })
                }
                placeholder="ATATT..."
                className={inputClass}
              />
            </Field>
          </>
        );
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close configuration"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
      />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl">
        <div className="flex items-start justify-between border-b border-zinc-800 px-5 py-5">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl ${app.accentBg}`}
            >
              <IntegrationLogo
                id={app.id}
                className={`h-6 w-6 ${app.iconClassName}`}
              />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">
                {connected ? "Configure" : "Connect"} {app.name}
              </h2>
              <p className="text-xs text-zinc-500">{app.syncsToCognee}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {renderFields()}
        </div>

        <div className="space-y-2 border-t border-zinc-800 px-5 py-4">
          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </p>
          )}
          {connected && (
            <button
              type="button"
              onClick={() => {
                disconnect(app.id);
                onClose();
              }}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-red-500/30 px-4 py-2.5 text-sm text-red-400 transition hover:bg-red-500/10"
            >
              <Unplug className="h-4 w-4" />
              Disconnect
            </button>
          )}
          <button
            type="button"
            disabled={saving}
            onClick={() => void handleSave()}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {connected ? "Save & re-sync" : "Save & connect"}
          </button>
        </div>
      </aside>
    </>
  );
}

export function useSelectedIntegration() {
  const [selectedId, setSelectedId] = useState<IntegrationId | null>(null);
  const selectedApp = INTEGRATION_CATALOG.find((app) => app.id === selectedId);

  return {
    selectedApp,
    open: (id: IntegrationId) => setSelectedId(id),
    close: () => setSelectedId(null),
  };
}
