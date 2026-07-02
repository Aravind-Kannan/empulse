"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ExternalLink, Loader2, Unplug, X } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  connectJiraIntegration,
  saveGitHubIntegrationConfig,
  saveNotionIntegrationConfig,
  saveSlackIntegrationConfig,
  syncIntegrationSource,
  validateJiraIntegration,
  validateNotionIntegration,
  validateSlackIntegration,
} from "@/lib/api";
import { INTEGRATION_SETUP_GUIDES } from "@/lib/integration-setup-guides";
import {
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  isIntegrationDraft,
  normalizeJiraSiteUrl,
  parseJiraProjectKeys,
  validateJiraConfigDraft,
  type IntegrationDefinition,
  type IntegrationId,
} from "@/lib/integrations";

import { IntegrationLogo } from "./IntegrationLogos";
import { SecretInput } from "./SecretInput";

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

function SetupGuide({ integrationId }: { integrationId: IntegrationId }) {
  const guide = INTEGRATION_SETUP_GUIDES[integrationId];

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
      <p className="text-sm font-medium text-zinc-200">{guide.title}</p>
      <ol className="mt-3 list-decimal space-y-2 pl-4 text-xs leading-relaxed text-zinc-400">
        {guide.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      {guide.docUrl && (
        <a
          href={guide.docUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300"
        >
          {guide.docLabel ?? "Documentation"}
          <ExternalLink className="h-3 w-3" />
        </a>
      )}
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500";

type ConnectStepId = "validate" | "save" | "sync" | "refresh";

interface ConnectStep {
  id: ConnectStepId;
  label: string;
  status: "pending" | "active" | "done";
}

function buildConnectSteps(
  integrationId: IntegrationId,
  integrationName: string,
): ConnectStep[] {
  const steps: ConnectStep[] = [];

  if (
    integrationId === "notion" ||
    integrationId === "slack" ||
    integrationId === "jira"
  ) {
    steps.push({
      id: "validate",
      label: `Calling ${integrationName} API to verify credentials`,
      status: "pending",
    });
  }

  const saveLabel =
    integrationId === "github"
      ? `Verifying credentials with ${integrationName} API and saving configuration`
      : integrationId === "jira"
        ? "Saving Jira configuration"
        : "Saving integration configuration";

  steps.push(
    { id: "save", label: saveLabel, status: "pending" },
    {
      id: "sync",
      label:
        integrationId === "jira"
          ? "Queuing background sync into knowledge graph"
          : `Fetching ${integrationName} data and syncing into knowledge graph`,
      status: "pending",
    },
    {
      id: "refresh",
      label: "Refreshing workspace telemetry and dashboards",
      status: "pending",
    },
  );

  return steps;
}

function advanceStep(
  steps: ConnectStep[],
  activeId: ConnectStepId,
): ConnectStep[] {
  let passedActive = false;
  return steps.map((step) => {
    if (step.id === activeId) {
      passedActive = true;
      return { ...step, status: "active" };
    }
    if (!passedActive) {
      return { ...step, status: "done" };
    }
    return step;
  });
}

function completeStep(steps: ConnectStep[], doneId: ConnectStepId): ConnectStep[] {
  let passedDone = false;
  return steps.map((step) => {
    if (step.id === doneId) {
      passedDone = true;
      return { ...step, status: "done" };
    }
    if (passedDone) {
      return step;
    }
    return { ...step, status: "done" };
  });
}

function ConnectProgressPanel({ steps }: { steps: ConnectStep[] }) {
  return (
    <div
      className="rounded-lg border border-sky-500/25 bg-sky-500/5 px-3 py-3"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-sky-300">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Connecting {steps.some((s) => s.status === "active") ? "in progress" : "…"}
      </div>
      <ol className="space-y-2">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-2 text-xs">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
              {step.status === "done" ? (
                <span className="text-emerald-400" aria-hidden>
                  ✓
                </span>
              ) : step.status === "active" ? (
                <Loader2
                  className="h-3.5 w-3.5 animate-spin text-sky-400"
                  aria-hidden
                />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-zinc-600" aria-hidden />
              )}
            </span>
            <span
              className={
                step.status === "active"
                  ? "text-zinc-100"
                  : step.status === "done"
                    ? "text-zinc-500 line-through"
                    : "text-zinc-500"
              }
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
        This can take up to a minute while we call external APIs and build the
        graph. Please keep this panel open.
      </p>
    </div>
  );
}

export function IntegrationConfigDrawer({
  app,
  onClose,
}: IntegrationConfigDrawerProps) {
  const { config, updateConfig, disconnect } = useIntegrations();
  const { refreshOperationalState } = useWorkspace();
  const [saving, setSaving] = useState(false);
  const [connectSteps, setConnectSteps] = useState<ConnectStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const connected = isIntegrationConnected(app.id, config);
  const draft = isIntegrationDraft(app.id, config);
  const [mounted, setMounted] = useState(false);
  const isBusy = saving;

  function beginStep(stepId: ConnectStepId) {
    setConnectSteps((prev) => advanceStep(prev, stepId));
  }

  function finishStep(stepId: ConnectStepId) {
    setConnectSteps((prev) => completeStep(prev, stepId));
  }

  async function handleSave() {
    const steps = buildConnectSteps(app.id, app.name);
    setConnectSteps(steps);
    setSaving(true);
    setError(null);
    setSuccess(null);

    const runStep = async (stepId: ConnectStepId, action: () => Promise<void>) => {
      beginStep(stepId);
      await action();
      finishStep(stepId);
    };

    try {
      if (app.id === "notion") {
        if (!config.notion.integrationToken.trim()) {
          throw new Error("Notion integration token is required.");
        }
        let message = "";
        await runStep("validate", async () => {
          message = await validateNotionIntegration(config.notion.integrationToken);
        });
        await runStep("save", async () => {
          await saveNotionIntegrationConfig({
            ...config.notion,
            validated: true,
            previouslyConnected: true,
          });
          updateConfig("notion", { validated: true, previouslyConnected: true });
        });
        await runStep("sync", async () => {
          await syncIntegrationSource("notion");
        });
        setSuccess(`${message} Connected and synced.`);
      } else if (app.id === "slack") {
        if (!config.slack.botToken.trim()) {
          throw new Error("Slack bot token is required.");
        }
        let message = "";
        await runStep("validate", async () => {
          message = await validateSlackIntegration(config.slack.botToken);
        });
        await runStep("save", async () => {
          await saveSlackIntegrationConfig({
            ...config.slack,
            validated: true,
            previouslyConnected: true,
          });
          updateConfig("slack", { validated: true, previouslyConnected: true });
        });
        await runStep("sync", async () => {
          await syncIntegrationSource("slack");
        });
        setSuccess(`${message} Connected and synced.`);
      } else if (app.id === "github") {
        if (!config.github.repositoryUrl.trim()) {
          throw new Error("GitHub repository URL is required.");
        }
        if (
          !config.github.personalAccessToken.trim() &&
          !config.github.previouslyConnected
        ) {
          throw new Error("GitHub personal access token is required.");
        }
        let message = "";
        await runStep("save", async () => {
          message = await saveGitHubIntegrationConfig({
            ...config.github,
            oauthConnected: false,
            validated: true,
            previouslyConnected: true,
          });
          updateConfig("github", {
            oauthConnected: false,
            validated: true,
            previouslyConnected: true,
          });
        });
        await runStep("sync", async () => {
          await syncIntegrationSource("github");
        });
        setSuccess(`${message} Connected and synced.`);
      } else if (app.id === "jira") {
        const validationError = validateJiraConfigDraft(config.jira);
        if (validationError) {
          throw new Error(validationError);
        }
        const normalizedSite = normalizeJiraSiteUrl(config.jira.siteUrl);
        const normalizedKeys = parseJiraProjectKeys(config.jira.projectKeys).join(
          ", ",
        );
        const jiraDraft = {
          ...config.jira,
          siteUrl: normalizedSite,
          projectKeys: normalizedKeys,
        };
        let message = "";
        await runStep("validate", async () => {
          message = await validateJiraIntegration(jiraDraft);
        });
        await runStep("save", async () => {
          await connectJiraIntegration(jiraDraft);
          updateConfig("jira", {
            siteUrl: normalizedSite,
            projectKeys: normalizedKeys,
            validated: true,
            previouslyConnected: true,
          });
        });
        await runStep("sync", async () => {
          // connectJiraIntegration queues Cognee sync on the server.
        });
        setSuccess(`${message} Cognee sync has started in the background.`);
      }

      await runStep("refresh", async () => {
        await refreshOperationalState();
      });

      setConnectSteps([]);
      setSaving(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integration");
      setConnectSteps([]);
      setSaving(false);
    }
  }

  useEffect(() => {
    setMounted(true);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  function handleRequestClose() {
    if (isBusy) return;
    onClose();
  }

  function renderFields() {
    switch (app.id) {
      case "slack":
        return (
          <>
            <SetupGuide integrationId="slack" />
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
            <Field
              label="Bot token"
              hint="Bot User OAuth Token (xoxb-…). Verified via Slack auth.test on save."
            >
              <SecretInput
                value={config.slack.botToken}
                onChange={(value) => updateConfig("slack", { botToken: value })}
                placeholder="xoxb-..."
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
            <SetupGuide integrationId="notion" />
            <Field
              label="Integration token"
              hint="Internal Integration Secret (secret_… or ntn_…). Verified via Notion API on save."
            >
              <SecretInput
                value={config.notion.integrationToken}
                onChange={(value) =>
                  updateConfig("notion", { integrationToken: value })
                }
                placeholder="secret_..."
              />
            </Field>
            <Field
              label="Limit to database IDs (optional)"
              hint="Leave empty to auto-discover all shared databases. Comma-separated IDs to restrict import."
            >
              <input
                type="text"
                value={config.notion.databaseIds}
                onChange={(e) =>
                  updateConfig("notion", { databaseIds: e.target.value })
                }
                placeholder="Leave empty for auto-discovery"
                className={inputClass}
              />
            </Field>
          </>
        );

      case "github":
        return (
          <>
            <SetupGuide integrationId="github" />
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
              hint="Fine-grained or classic token with repo read scope. Verified via GitHub API on save."
            >
              <SecretInput
                value={config.github.personalAccessToken}
                onChange={(value) =>
                  updateConfig("github", {
                    personalAccessToken: value,
                    oauthConnected: false,
                  })
                }
                placeholder="ghp_..."
              />
            </Field>
          </>
        );

      case "jira":
        return (
          <>
            <SetupGuide integrationId="jira" />
            <Field
              label="Site domain / instance URL"
              hint="Your Atlassian Cloud site, e.g. https://acme.atlassian.net"
            >
              <input
                type="url"
                value={config.jira.siteUrl}
                onChange={(e) =>
                  updateConfig("jira", { siteUrl: e.target.value })
                }
                onBlur={() =>
                  updateConfig("jira", {
                    siteUrl: normalizeJiraSiteUrl(config.jira.siteUrl),
                  })
                }
                placeholder="https://acme.atlassian.net"
                className={inputClass}
              />
            </Field>
            <Field
              label="Atlassian account email"
              hint="Email for your Atlassian account — paired with the API token for authentication"
            >
              <input
                type="email"
                value={config.jira.authEmail}
                onChange={(e) =>
                  updateConfig("jira", { authEmail: e.target.value })
                }
                placeholder="you@company.com"
                className={inputClass}
                autoComplete="email"
              />
            </Field>
            <Field
              label="Target project keys (optional)"
              hint="Comma-separated keys (ENG, PLAT). Leave empty to import all accessible projects."
            >
              <input
                type="text"
                value={config.jira.projectKeys}
                onChange={(e) =>
                  updateConfig("jira", { projectKeys: e.target.value })
                }
                onBlur={() => {
                  try {
                    const keys = parseJiraProjectKeys(config.jira.projectKeys);
                    updateConfig("jira", { projectKeys: keys.join(", ") });
                  } catch {
                    // keep raw value so save surfaces the validation error
                  }
                }}
                placeholder="Leave empty for all projects"
                className={inputClass}
              />
            </Field>
            <Field
              label="Account email"
              hint="Atlassian account email for this API token (not your Empulse login)"
            >
              <input
                type="email"
                value={config.jira.accountEmail}
                onChange={(e) =>
                  updateConfig("jira", { accountEmail: e.target.value })
                }
                placeholder="you@company.com"
                className={inputClass}
              />
            </Field>
            <Field
              label="API access token"
              hint="Atlassian API token from id.atlassian.com — verified via Jira API on save"
            >
              <SecretInput
                value={config.jira.apiToken}
                onChange={(value) => updateConfig("jira", { apiToken: value })}
                placeholder="ATATT..."
              />
            </Field>
          </>
        );
    }
  }

  const drawer = (
    <>
      <button
        type="button"
        aria-label="Close configuration"
        className="fixed inset-0 z-[100] bg-black/50"
        onClick={handleRequestClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="integration-drawer-title"
        className="fixed inset-y-0 right-0 z-[101] flex w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-zinc-800 px-5 py-5">
          <div className="flex min-w-0 items-center gap-3">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl ${app.accentBg}`}
            >
              <IntegrationLogo
                id={app.id}
                className={`h-6 w-6 ${app.iconClassName}`}
              />
            </div>
            <div className="min-w-0">
              <h2
                id="integration-drawer-title"
                className="text-lg font-semibold text-zinc-100"
              >
                {connected ? "Configure" : "Connect"} {app.name}
              </h2>
              <p className="text-xs text-zinc-500">{app.syncsToCognee}</p>
              {draft && !connected && !isBusy && (
                <p className="mt-1 text-xs text-amber-400/90">
                  Token entered — click Save to verify with {app.name}.
                </p>
              )}
              {saving && (
                <p className="mt-1 text-xs text-sky-400/90">
                  Connection in progress — do not close this panel.
                </p>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={handleRequestClose}
            disabled={isBusy}
            className="ml-3 shrink-0 rounded-lg p-1.5 text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {renderFields()}
        </div>

        <div className="shrink-0 space-y-2 border-t border-zinc-800 px-5 py-4">
          {saving && connectSteps.length > 0 && (
            <ConnectProgressPanel steps={connectSteps} />
          )}
          {success && (
            <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">
              {success}
            </p>
          )}
          {error && (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </p>
          )}
          {connected && !isBusy && (
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
            disabled={isBusy}
            onClick={() => void handleSave()}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50"
          >
            {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving
              ? "Connecting…"
              : connected
                ? "Save & re-verify"
                : "Save & verify connection"}
          </button>
        </div>
      </aside>
    </>
  );

  if (!mounted) {
    return null;
  }

  return createPortal(drawer, document.body);
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
