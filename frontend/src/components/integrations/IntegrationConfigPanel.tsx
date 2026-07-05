"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Loader2, Unplug } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import { useWorkspace } from "@/context/WorkspaceContext";
import {
  discoverGitHubRepositories,
  discoverJiraProjects,
  listGitHubRepositoryBranches,
  saveGitHubIntegrationConfig,
  saveJiraIntegrationConfig,
  saveNotionIntegrationConfig,
  saveSlackIntegrationConfig,
  syncIntegrationSource,
  validateJiraIntegration,
  validateNotionIntegration,
  validateSlackIntegration,
  type GitHubDiscoveredRepo,
  type JiraDiscoveredProject,
} from "@/lib/api";
import { INTEGRATION_SETUP_GUIDES } from "@/lib/integration-setup-guides";
import {
  isIntegrationConnected,
  isIntegrationDraft,
  normalizeJiraSiteUrl,
  parseJiraProjectKeys,
  parseGitHubBranchTargets,
  validateJiraConfigDraft,
  type IntegrationDefinition,
  type IntegrationId,
} from "@/lib/integrations";

import { IntegrationSearchMultiSelect } from "./IntegrationSearchMultiSelect";
import { SecretInput } from "./SecretInput";

export type ConnectMode = "full" | "credentials-only";

interface IntegrationConfigPanelProps {
  app: IntegrationDefinition;
  variant?: "page" | "drawer";
  connectMode?: ConnectMode;
  onDisconnectComplete?: () => void;
  onSaveComplete?: () => void;
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
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 backdrop-blur-sm">
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

export const integrationInputClass =
  "w-full rounded-lg border border-zinc-700/80 bg-zinc-950/80 px-3 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500/30";

type ConnectStepId = "validate" | "save" | "sync" | "refresh";

interface ConnectStep {
  id: ConnectStepId;
  label: string;
  status: "pending" | "active" | "done";
}

function buildConnectSteps(
  integrationId: IntegrationId,
  integrationName: string,
  connectMode: ConnectMode,
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

  steps.push({ id: "save", label: saveLabel, status: "pending" });

  if (connectMode === "full") {
    steps.push(
      {
        id: "sync",
        label:
          integrationId === "jira"
            ? "Queuing background sync"
            : `Queuing ${integrationName} sync`,
        status: "pending",
      },
      {
        id: "refresh",
        label: "Refreshing workspace telemetry and dashboards",
        status: "pending",
      },
    );
  }

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

function ConnectProgressPanel({
  steps,
  credentialsOnly = false,
}: {
  steps: ConnectStep[];
  credentialsOnly?: boolean;
}) {
  return (
    <div
      className="rounded-xl border border-sky-500/25 bg-sky-500/5 px-4 py-3"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="mb-2 flex items-center gap-2 text-xs font-medium text-sky-300">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        {credentialsOnly ? "Verifying" : "Connecting"}{" "}
        {steps.some((s) => s.status === "active") ? "in progress" : "…"}
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
      {!credentialsOnly && (
        <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
          Sync runs in the background. Large GitHub repos can take several minutes —
          track progress on the Runs tab.
        </p>
      )}
    </div>
  );
}

const CREDENTIALS_ONLY_SUCCESS =
  "Credentials verified and saved. Start sync from your dashboard.";

export function IntegrationConfigPanel({
  app,
  variant = "page",
  connectMode = "full",
  onDisconnectComplete,
  onSaveComplete,
}: IntegrationConfigPanelProps) {
  const { config, updateConfig, disconnect, refreshSyncJobs } = useIntegrations();
  const { refreshOperationalState } = useWorkspace();
  const [saving, setSaving] = useState(false);
  const [connectSteps, setConnectSteps] = useState<ConnectStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const connected = isIntegrationConnected(app.id, config);
  const draft = isIntegrationDraft(app.id, config);
  const [discoveredRepos, setDiscoveredRepos] = useState<GitHubDiscoveredRepo[]>([]);
  const [repoSearch, setRepoSearch] = useState("");
  const [discoveringRepos, setDiscoveringRepos] = useState(false);
  const [discoveredJiraProjects, setDiscoveredJiraProjects] = useState<
    JiraDiscoveredProject[]
  >([]);
  const [jiraProjectSearch, setJiraProjectSearch] = useState("");
  const [discoveringJiraProjects, setDiscoveringJiraProjects] = useState(false);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [branchInput, setBranchInput] = useState("");
  const isBusy = saving;
  const credentialsOnly = connectMode === "credentials-only";

  function beginStep(stepId: ConnectStepId) {
    setConnectSteps((prev) => advanceStep(prev, stepId));
  }

  function finishStep(stepId: ConnectStepId) {
    setConnectSteps((prev) => completeStep(prev, stepId));
  }

  async function handleSave() {
    const steps = buildConnectSteps(app.id, app.name, connectMode);
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
        if (!credentialsOnly) {
          await runStep("sync", async () => {
            await syncIntegrationSource("notion");
            await refreshSyncJobs();
          });
          setSuccess(`${message} Sync queued — check the Runs tab for progress.`);
        } else {
          setSuccess(CREDENTIALS_ONLY_SUCCESS);
        }
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
        if (!credentialsOnly) {
          await runStep("sync", async () => {
            await syncIntegrationSource("slack");
            await refreshSyncJobs();
          });
          setSuccess(`${message} Sync queued — check the Runs tab for progress.`);
        } else {
          setSuccess(CREDENTIALS_ONLY_SUCCESS);
        }
      } else if (app.id === "github") {
        const selectedRepos =
          config.github.repositoryUrls.length > 0
            ? config.github.repositoryUrls
            : config.github.repositoryUrl.trim()
              ? [config.github.repositoryUrl.trim()]
              : [];
        if (selectedRepos.length === 0) {
          throw new Error("Select at least one GitHub repository to sync.");
        }
        if (
          !config.github.personalAccessToken.trim() &&
          !config.github.previouslyConnected
        ) {
          throw new Error("GitHub personal access token is required.");
        }
        if (
          !config.github.syncAllBranches &&
          config.github.branchTargets.length === 0 &&
          !config.github.branchTarget.trim()
        ) {
          throw new Error(
            "Choose specific branches or enable sync for all branches.",
          );
        }

        const githubDraft = {
          ...config.github,
          repositoryUrls: selectedRepos,
          repositoryUrl: selectedRepos[0],
          branchTargets: config.github.syncAllBranches
            ? []
            : config.github.branchTargets.length > 0
              ? config.github.branchTargets
              : parseGitHubBranchTargets(config.github.branchTarget),
          branchTarget:
            config.github.branchTargets[0] ?? config.github.branchTarget ?? "main",
        };

        let message = "";
        await runStep("save", async () => {
          message = await saveGitHubIntegrationConfig({
            ...githubDraft,
            oauthConnected: false,
            validated: true,
            previouslyConnected: true,
          });
          updateConfig("github", {
            ...githubDraft,
            oauthConnected: false,
            validated: true,
            previouslyConnected: true,
          });
        });
        if (!credentialsOnly) {
          await runStep("sync", async () => {
            await syncIntegrationSource("github");
            await refreshSyncJobs();
          });
          setSuccess(`${message} Sync queued — check the Runs tab for progress.`);
        } else {
          setSuccess(CREDENTIALS_ONLY_SUCCESS);
        }
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
          await saveJiraIntegrationConfig(jiraDraft);
          updateConfig("jira", {
            siteUrl: normalizedSite,
            projectKeys: normalizedKeys,
            validated: true,
            previouslyConnected: true,
          });
        });
        if (!credentialsOnly) {
          await runStep("sync", async () => {
            await syncIntegrationSource("jira");
          });
          setSuccess(`${message} Connected and synced.`);
        } else {
          setSuccess(CREDENTIALS_ONLY_SUCCESS);
        }
      }

      if (!credentialsOnly) {
        await runStep("refresh", async () => {
          await refreshOperationalState();
        });
      }

      setConnectSteps([]);
      setSaving(false);
      if (credentialsOnly) {
        onSaveComplete?.();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integration");
      setConnectSteps([]);
      setSaving(false);
    }
  }

  useEffect(() => {
    if (app.id !== "github") return;
    const targets =
      config.github.branchTargets.length > 0
        ? config.github.branchTargets
        : parseGitHubBranchTargets(config.github.branchTarget);
    setBranchInput(targets.join(", "));
  }, [
    app.id,
    config.github.branchTargets,
    config.github.branchTarget,
  ]);

  async function handleDiscoverGitHubRepos() {
    if (!config.github.personalAccessToken.trim()) {
      setError("Enter a GitHub personal access token first.");
      return;
    }

    setDiscoveringRepos(true);
    setError(null);
    try {
      const result = await discoverGitHubRepositories(
        config.github.personalAccessToken,
      );
      setDiscoveredRepos(result.repositories);
      if (result.repositories.length === 0) {
        setError(result.message);
      } else {
        setSuccess(result.message);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to discover repositories",
      );
    } finally {
      setDiscoveringRepos(false);
    }
  }

  async function handleLoadGitHubBranches() {
    const token = config.github.personalAccessToken.trim();
    const repositoryUrl =
      config.github.repositoryUrls[0] ?? config.github.repositoryUrl.trim();
    if (!token) {
      setError("Enter a GitHub personal access token first.");
      return;
    }
    if (!repositoryUrl) {
      setError("Select at least one repository before loading branches.");
      return;
    }

    setLoadingBranches(true);
    setError(null);
    try {
      const result = await listGitHubRepositoryBranches(token, repositoryUrl);
      const branches = result.branches.length > 0 ? result.branches : [result.default_branch];
      setBranchInput(branches.join(", "));
      updateConfig("github", {
        branchTargets: branches,
        branchTarget: result.default_branch,
        syncAllBranches: false,
      });
      setSuccess(`Loaded ${branches.length} branch(es) from ${repositoryUrl}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load branches");
    } finally {
      setLoadingBranches(false);
    }
  }

  async function handleDiscoverJiraProjects() {
    if (!config.jira.siteUrl.trim()) {
      setError("Jira site URL is required.");
      return;
    }
    if (!config.jira.authEmail.trim()) {
      setError("Atlassian account email is required.");
      return;
    }
    if (!config.jira.apiToken.trim()) {
      setError("Jira API token is required.");
      return;
    }

    setDiscoveringJiraProjects(true);
    setError(null);
    try {
      const result = await discoverJiraProjects({
        ...config.jira,
        siteUrl: normalizeJiraSiteUrl(config.jira.siteUrl),
      });
      setDiscoveredJiraProjects(result.projects);
      if (result.projects.length === 0) {
        setError(result.message);
      } else {
        setSuccess(result.message);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to discover Jira projects",
      );
    } finally {
      setDiscoveringJiraProjects(false);
    }
  }

  function updateJiraProjectKeys(keys: string[]) {
    updateConfig("jira", { projectKeys: keys.join(", ") });
  }

  function renderFields() {
    switch (app.id) {
      case "slack":
        return (
          <>
            <SetupGuide integrationId="slack" />
            <div className="rounded-xl border border-sky-900/40 bg-sky-950/20 p-3 text-xs leading-relaxed text-sky-200/90">
              All channels the bot has joined will be synced automatically. Re-sync
              anytime to pick up new channels.
            </div>
            <Field label="Workspace URL" hint="e.g. https://acme.slack.com">
              <input
                type="url"
                value={config.slack.workspaceUrl}
                onChange={(e) =>
                  updateConfig("slack", { workspaceUrl: e.target.value })
                }
                placeholder="https://your-team.slack.com"
                className={integrationInputClass}
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
            <details className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-3">
              <summary className="cursor-pointer text-sm text-zinc-300">
                Advanced: limit to channel IDs
              </summary>
              <div className="mt-3">
                <Field
                  label="Channel IDs (optional)"
                  hint="Leave empty for auto-discovery. Comma-separated IDs to restrict sync."
                >
                  <input
                    type="text"
                    value={config.slack.channelIds}
                    onChange={(e) =>
                      updateConfig("slack", { channelIds: e.target.value })
                    }
                    placeholder="Leave empty for auto-discovery"
                    className={integrationInputClass}
                  />
                </Field>
              </div>
            </details>
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
                className={integrationInputClass}
              />
            </Field>
          </>
        );

      case "github": {
        const repoItems = discoveredRepos.map((repo) => ({
          id: repo.html_url,
          label: repo.full_name,
          description: repo.description ?? undefined,
          badge: repo.private ? "private" : undefined,
        }));

        return (
          <>
            <SetupGuide integrationId="github" />
            <Field
              label="Personal access token (PAT)"
              hint="Fine-grained or classic token with repository read scope. Used to discover repositories accessible to your account."
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
            <div>
              <button
                type="button"
                disabled={discoveringRepos || isBusy}
                onClick={() => void handleDiscoverGitHubRepos()}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 transition hover:border-zinc-500 disabled:opacity-50"
              >
                {discoveringRepos && <Loader2 className="h-4 w-4 animate-spin" />}
                {discoveringRepos ? "Loading repositories…" : "Load accessible repositories"}
              </button>
            </div>
            <Field
              label="Repositories to sync"
              hint="Search and select repositories Empulse should pull PR activity from."
            >
              <IntegrationSearchMultiSelect
                items={repoItems}
                selectedIds={config.github.repositoryUrls}
                onChange={(repositoryUrls) =>
                  updateConfig("github", {
                    repositoryUrls,
                    repositoryUrl: repositoryUrls[0] ?? "",
                  })
                }
                searchQuery={repoSearch}
                onSearchChange={setRepoSearch}
                emptyMessage="Load repositories after entering your PAT. Previously saved selections are kept even if you do not reload the list."
                searchPlaceholder="Search repositories…"
                inputClassName={integrationInputClass}
              />
            </Field>
            <Field
              label="Branch sync mode"
              hint="Sync merged PRs targeting all branches, or restrict to a specific list."
            >
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm text-zinc-200">
                  <input
                    type="radio"
                    name="github-branch-mode"
                    checked={config.github.syncAllBranches}
                    onChange={() =>
                      updateConfig("github", { syncAllBranches: true })
                    }
                  />
                  All branches
                </label>
                <label className="flex items-center gap-2 text-sm text-zinc-200">
                  <input
                    type="radio"
                    name="github-branch-mode"
                    checked={!config.github.syncAllBranches}
                    onChange={() =>
                      updateConfig("github", { syncAllBranches: false })
                    }
                  />
                  Specific branches
                </label>
              </div>
            </Field>
            <Field
              label="File content & patches"
              hint="Off by default. When enabled, full file bodies and diff patches are stored. Paths, blame, commit history, and authors always sync."
            >
              <label className="flex items-center gap-2 text-sm text-zinc-200">
                <input
                  type="checkbox"
                  checked={config.github.ingestFileContent}
                  onChange={(event) =>
                    updateConfig("github", {
                      ingestFileContent: event.target.checked,
                    })
                  }
                />
                Store full file contents and diff patches
              </label>
            </Field>
            {!config.github.syncAllBranches && (
              <Field
                label="Target branches"
                hint="Comma-separated branch names applied across selected repositories (e.g. main, develop)."
              >
                <input
                  type="text"
                  value={branchInput}
                  onChange={(e) => {
                    const value = e.target.value;
                    setBranchInput(value);
                    const branchTargets = parseGitHubBranchTargets(value);
                    updateConfig("github", {
                      branchTargets,
                      branchTarget: branchTargets[0] ?? "main",
                    });
                  }}
                  placeholder="main, develop"
                  className={integrationInputClass}
                />
                <button
                  type="button"
                  disabled={loadingBranches || isBusy}
                  onClick={() => void handleLoadGitHubBranches()}
                  className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 transition hover:border-zinc-500 disabled:opacity-50"
                >
                  {loadingBranches && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Load branches from first selected repository
                </button>
              </Field>
            )}
          </>
        );
      }

      case "jira": {
        const selectedProjectKeys = parseJiraProjectKeys(config.jira.projectKeys);
        const projectItems = discoveredJiraProjects.map((project) => ({
          id: project.key,
          label: `${project.key} — ${project.name}`,
          description: project.project_type ?? undefined,
        }));

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
                className={integrationInputClass}
              />
            </Field>
            <Field
              label="Atlassian account email"
              hint="Email for your Atlassian account — paired with the API token (not your Empulse login)"
            >
              <input
                type="email"
                value={config.jira.authEmail ?? ""}
                onChange={(e) =>
                  updateConfig("jira", { authEmail: e.target.value })
                }
                placeholder="you@company.com"
                className={integrationInputClass}
                autoComplete="off"
                data-1p-ignore
                data-lpignore="true"
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
            <div>
              <button
                type="button"
                disabled={discoveringJiraProjects || isBusy}
                onClick={() => void handleDiscoverJiraProjects()}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-sm text-zinc-100 transition hover:border-zinc-500 disabled:opacity-50"
              >
                {discoveringJiraProjects && (
                  <Loader2 className="h-4 w-4 animate-spin" />
                )}
                {discoveringJiraProjects
                  ? "Loading projects…"
                  : "Load accessible projects"}
              </button>
            </div>
            <Field
              label="Projects to sync"
              hint="Search and select projects. Leave none selected to import all accessible projects."
            >
              <IntegrationSearchMultiSelect
                items={projectItems}
                selectedIds={selectedProjectKeys}
                onChange={updateJiraProjectKeys}
                searchQuery={jiraProjectSearch}
                onSearchChange={setJiraProjectSearch}
                emptyMessage="Load projects after entering site URL, email, and API token. Previously saved selections are kept even if you do not reload the list."
                searchPlaceholder="Search projects…"
                inputClassName={integrationInputClass}
              />
            </Field>
          </>
        );
      }
    }
  }

  const isPage = variant === "page";
  const saveButtonLabel = saving
    ? credentialsOnly
      ? "Saving…"
      : "Connecting…"
    : connected
      ? credentialsOnly
        ? "Save & re-verify"
        : "Save & re-verify"
      : credentialsOnly
        ? "Save & verify"
        : "Save & verify connection";

  const statusBanner = (
    <>
      {(draft && !connected && !isBusy) || saving ? (
        <div className="space-y-1">
          {draft && !connected && !isBusy && (
            <p className="text-sm text-amber-400/90">
              Token entered — click Save to verify with {app.name}.
            </p>
          )}
          {saving && (
            <p className="text-sm text-sky-400/90">
              {credentialsOnly
                ? "Verifying credentials — stay on this page until complete."
                : "Connection in progress — stay on this page until complete."}
            </p>
          )}
        </div>
      ) : null}
    </>
  );

  const actionFooter = (
    <div
      className={
        isPage
          ? "space-y-3 border-t border-zinc-800/60 pt-6"
          : "space-y-2 border-t border-zinc-800/80 bg-slate-950 pt-4"
      }
    >
      {saving && connectSteps.length > 0 && (
        <ConnectProgressPanel steps={connectSteps} credentialsOnly={credentialsOnly} />
      )}
      {success && (
        <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
          {success}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {connected && !isBusy && (
          <button
            type="button"
            onClick={() => {
              disconnect(app.id);
              onDisconnectComplete?.();
            }}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-500/30 px-4 py-2.5 text-sm text-red-400 transition hover:bg-red-500/10 sm:order-first"
          >
            <Unplug className="h-4 w-4" />
            Disconnect
          </button>
        )}
        <button
          type="button"
          disabled={isBusy}
          onClick={() => void handleSave()}
          className={`inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-5 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50 ${isPage ? "sm:ml-auto" : "w-full"}`}
        >
          {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
          {saveButtonLabel}
        </button>
      </div>
    </div>
  );

  if (!isPage) {
    return (
      <form
        autoComplete="off"
        onSubmit={(event) => event.preventDefault()}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          {statusBanner}
          {renderFields()}
        </div>
        <div className="shrink-0">{actionFooter}</div>
      </form>
    );
  }

  return (
    <form
      autoComplete="off"
      onSubmit={(event) => event.preventDefault()}
      className="space-y-6 rounded-2xl border border-zinc-800/80 bg-zinc-950/30 p-6 backdrop-blur-sm lg:p-8"
    >
      {statusBanner}
      <div className="space-y-5">{renderFields()}</div>
      {actionFooter}
    </form>
  );
}
