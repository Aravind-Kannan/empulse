export type IntegrationId = "slack" | "notion" | "github" | "jira";

export type IntegrationStatus =
  | "connected"
  | "available"
  | "disconnected"
  | "syncing"
  | "pending";

export interface SlackConfig {
  workspaceUrl: string;
  botToken: string;
  channelIds: string;
  /** Set true only after a successful API validation on save */
  validated?: boolean;
  /** True after the user has verified or saved this integration at least once */
  previouslyConnected?: boolean;
}

export interface NotionConfig {
  integrationToken: string;
  databaseIds: string;
  validated?: boolean;
  previouslyConnected?: boolean;
}

export interface GitHubConfig {
  repositoryUrl: string;
  repositoryUrls: string[];
  branchTarget: string;
  branchTargets: string[];
  syncAllBranches: boolean;
  personalAccessToken: string;
  oauthConnected: boolean;
  validated?: boolean;
  previouslyConnected?: boolean;
}

export interface JiraConfig {
  siteUrl: string;
  authEmail: string;
  projectKeys: string;
  apiToken: string;
  validated?: boolean;
  previouslyConnected?: boolean;
}

export type IntegrationConfigMap = {
  slack: SlackConfig;
  notion: NotionConfig;
  github: GitHubConfig;
  jira: JiraConfig;
};

export interface IntegrationDefinition {
  id: IntegrationId;
  name: string;
  description: string;
  syncsToCognee: string;
  /** Concrete data pulled during graph sync (matches backend fetch scope). */
  syncPullItems: string[];
  accent: string;
  accentBg: string;
  iconClassName: string;
}

export const INTEGRATION_CATALOG: IntegrationDefinition[] = [
  {
    id: "slack",
    name: "Slack",
    description: "Incident threads, on-call channels, and engineering announcements.",
    syncsToCognee:
      "Incident thread metadata and on-call channel activity into the knowledge graph.",
    syncPullItems: [
      "Incident & on-call channel threads (90-day lookback)",
      "Thread titles, channel names, and resolver identity",
      "resolvedBy and discussesComponent graph edges",
      "No message bodies stored — metadata only",
    ],
    accent: "text-[#E01E5A]",
    accentBg: "bg-[#4A154B]",
    iconClassName: "text-white",
  },
  {
    id: "notion",
    name: "Notion",
    description: "Runbooks, architecture docs, and team wikis.",
    syncsToCognee:
      "Documentation pages and authorship links for coverage analytics.",
    syncPullItems: [
      "Pages from workspace search and configured databases",
      "Runbook & architecture doc titles and ownership tags",
      "documentedBy and authoredBy links to components & people",
      "Documentation coverage telemetry vs GitHub activity",
    ],
    accent: "text-zinc-100",
    accentBg: "bg-transparent",
    iconClassName: "text-white",
  },
  {
    id: "github",
    name: "GitHub",
    description: "Repositories, pull requests, and code ownership.",
    syncsToCognee:
      "Pull requests, file diffs, source code, and blame ownership into the knowledge graph.",
    syncPullItems: [
      "Merged PRs from configured repos & branches (6-month window)",
      "Per-PR file paths, LOC changes, and diff patch previews",
      "Source file contents (up to 40 mapped files per sync)",
      "Git blame line ranges and primary author attribution",
      "contributedTo, modifies, documentsComponent, and blameAttributedTo edges",
    ],
    accent: "text-zinc-100",
    accentBg: "bg-[#24292f]",
    iconClassName: "text-white",
  },
  {
    id: "jira",
    name: "Jira",
    description: "Sprints, epics, and operational work items.",
    syncsToCognee:
      "Open issue metadata and assignee links into the knowledge graph.",
    syncPullItems: [
      "Open issues from configured project keys",
      "Ticket type, priority, status, and assignee",
      "assignedTo and blocksComponent graph edges",
      "Backlog & high-priority telemetry (done issues skipped)",
    ],
    accent: "text-[#2684FF]",
    accentBg: "bg-transparent",
    iconClassName: "",
  },
];

export const DEFAULT_INTEGRATION_CONFIG: IntegrationConfigMap = {
  slack: { workspaceUrl: "", botToken: "", channelIds: "" },
  notion: { integrationToken: "", databaseIds: "" },
  github: {
    repositoryUrl: "",
    repositoryUrls: [],
    branchTarget: "main",
    branchTargets: [],
    syncAllBranches: false,
    personalAccessToken: "",
    oauthConnected: false,
  },
  jira: { siteUrl: "", authEmail: "", projectKeys: "", apiToken: "" },
};

function jiraAuthEmail(config: JiraConfig): string {
  return config.authEmail.trim();
}

const JIRA_SITE_RE =
  /^https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9]*\.atlassian\.net\/?$/i;
const PROJECT_KEY_RE = /^[A-Z][A-Z0-9]{0,9}$/;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeJiraSiteUrl(raw: string): string {
  let cleaned = raw.trim().replace(/\/+$/, "");
  if (!cleaned) return "";
  if (!/^https?:\/\//i.test(cleaned)) {
    cleaned = `https://${cleaned}`;
  }
  return cleaned;
}

export function parseJiraProjectKeys(raw: string): string[] {
  if (!raw.trim()) return [];
  const keys: string[] = [];
  for (const part of raw.split(",")) {
    const key = part.trim().toUpperCase();
    if (!key) continue;
    if (!PROJECT_KEY_RE.test(key)) {
      throw new Error(
        `Invalid project key "${part.trim()}". Use comma-separated keys like ENG, PLAT.`,
      );
    }
    if (!keys.includes(key)) keys.push(key);
  }
  return keys;
}

export function parseGitHubBranchTargets(raw: string): string[] {
  const branches: string[] = [];
  for (const part of raw.split(",")) {
    const branch = part.trim();
    if (!branch) continue;
    if (!branches.includes(branch)) branches.push(branch);
  }
  return branches;
}

/** Returns an error message when the draft config is invalid, otherwise null. */
export function validateJiraConfigDraft(config: JiraConfig): string | null {
  const siteUrl = normalizeJiraSiteUrl(config.siteUrl);
  if (!siteUrl) {
    return "Jira site URL is required.";
  }
  if (!JIRA_SITE_RE.test(siteUrl)) {
    return "Enter a valid Atlassian Cloud URL, e.g. https://acme.atlassian.net";
  }
  const email = jiraAuthEmail(config);
  if (!email) {
    return "Atlassian account email is required for API authentication.";
  }
  if (!EMAIL_RE.test(email)) {
    return "Enter a valid Atlassian account email.";
  }
  if (!config.apiToken.trim()) {
    return "Jira API token is required.";
  }
  try {
    parseJiraProjectKeys(config.projectKeys);
  } catch (err) {
    return err instanceof Error ? err.message : "Invalid project keys.";
  }
  return null;
}

export function wasPreviouslyConnected(
  id: IntegrationId,
  config: IntegrationConfigMap,
): boolean {
  return Boolean(config[id].previouslyConnected);
}

export function isIntegrationConnected(
  id: IntegrationId,
  config: IntegrationConfigMap,
): boolean {
  switch (id) {
    case "slack":
      return Boolean(config.slack.botToken.trim() && config.slack.validated);
    case "notion":
      return Boolean(
        config.notion.integrationToken.trim() && config.notion.validated,
      );
    case "github":
      return Boolean(
        (config.github.repositoryUrls.length > 0 ||
          config.github.repositoryUrl.trim()) &&
          (config.github.personalAccessToken.trim() ||
            config.github.oauthConnected) &&
          config.github.validated,
      );
    case "jira":
      return Boolean(
        config.jira.siteUrl.trim() &&
          jiraAuthEmail(config.jira) &&
          config.jira.apiToken.trim() &&
          config.jira.validated,
      );
  }
}

/** Credentials entered locally but not yet verified against the provider API */
export function isIntegrationDraft(
  id: IntegrationId,
  config: IntegrationConfigMap,
): boolean {
  if (isIntegrationConnected(id, config)) return false;
  switch (id) {
    case "slack":
      return Boolean(config.slack.botToken.trim());
    case "notion":
      return Boolean(config.notion.integrationToken.trim());
    case "github":
      return Boolean(
        (config.github.repositoryUrls.length > 0 ||
          config.github.repositoryUrl.trim()) &&
          (config.github.personalAccessToken.trim() ||
            config.github.oauthConnected),
      );
    case "jira":
      return Boolean(
        config.jira.siteUrl.trim() &&
          jiraAuthEmail(config.jira) &&
          config.jira.apiToken.trim(),
      );
  }
}

/** Integrations that can seed the member roster (flat hierarchy). */
export const MEMBER_IMPORT_SOURCES: IntegrationId[] = [
  "slack",
  "notion",
  "github",
  "jira",
];

export const MEMBER_IMPORT_SOURCE_LABEL =
  "Slack, Notion, GitHub, or Jira";

/** @deprecated Use MEMBER_IMPORT_SOURCES */
export const PEOPLE_INTEGRATION_IDS = MEMBER_IMPORT_SOURCES;

export function getConnectedMemberImportSources(
  config: IntegrationConfigMap,
): IntegrationId[] {
  return MEMBER_IMPORT_SOURCES.filter((id) => isIntegrationConnected(id, config));
}

/** @deprecated Use getConnectedMemberImportSources */
export function getConnectedPeopleSources(config: IntegrationConfigMap): IntegrationId[] {
  return getConnectedMemberImportSources(config);
}

export function hasMemberImportSourceConnected(
  config: IntegrationConfigMap,
): boolean {
  return getConnectedMemberImportSources(config).length > 0;
}

/** @deprecated Use hasMemberImportSourceConnected */
export function hasPeopleSourceConnected(config: IntegrationConfigMap): boolean {
  return hasMemberImportSourceConnected(config);
}

export function getConnectedIntegrationIds(
  config: IntegrationConfigMap,
): IntegrationId[] {
  return INTEGRATION_CATALOG.filter((app) =>
    isIntegrationConnected(app.id, config),
  ).map((app) => app.id);
}

export const WORKSPACE_INTEGRATION_REQUIREMENTS: Partial<
  Record<string, IntegrationId[]>
> = {
  "/era": MEMBER_IMPORT_SOURCES,
  "/exit": MEMBER_IMPORT_SOURCES,
  "/kra": ["github"],
  "/investigation": ["jira"],
};

export function workspaceRequiresIntegrations(path: string): IntegrationId[] {
  const match = Object.entries(WORKSPACE_INTEGRATION_REQUIREMENTS).find(
    ([prefix]) => path === prefix || path.startsWith(`${prefix}/`),
  );
  return match?.[1] ?? [];
}

export function isWorkspaceUnlocked(
  path: string,
  config: IntegrationConfigMap,
): boolean {
  const required = workspaceRequiresIntegrations(path);
  if (required.length === 0) return true;
  return required.some((id) => isIntegrationConnected(id, config));
}
