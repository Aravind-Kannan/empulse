export type IntegrationId = "slack" | "notion" | "github" | "jira";

export type IntegrationStatus = "connected" | "disconnected" | "syncing";

export interface SlackConfig {
  workspaceUrl: string;
  botToken: string;
  channelIds: string;
}

export interface NotionConfig {
  integrationToken: string;
  databaseIds: string;
}

export interface GitHubConfig {
  repositoryUrl: string;
  branchTarget: string;
  personalAccessToken: string;
  oauthConnected: boolean;
}

export interface JiraConfig {
  siteUrl: string;
  projectKeys: string;
  apiToken: string;
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
      "Channel metadata, incident threads, and on-call rotations into the knowledge graph.",
    accent: "text-[#E01E5A]",
    accentBg: "bg-[#4A154B]",
    iconClassName: "text-white",
  },
  {
    id: "notion",
    name: "Notion",
    description: "Runbooks, architecture docs, and team wikis.",
    syncsToCognee:
      "Page hierarchy, runbook content, and ownership tags for documentation coverage.",
    accent: "text-zinc-100",
    accentBg: "bg-transparent",
    iconClassName: "text-white",
  },
  {
    id: "github",
    name: "GitHub",
    description: "Repositories, pull requests, and code ownership.",
    syncsToCognee:
      "Repo structure, CODEOWNERS, PR history, and branch protection metadata.",
    accent: "text-zinc-100",
    accentBg: "bg-[#24292f]",
    iconClassName: "text-white",
  },
  {
    id: "jira",
    name: "Jira",
    description: "Sprints, epics, and operational work items.",
    syncsToCognee:
      "Project keys, issue links, sprint velocity, and component assignment edges.",
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
    branchTarget: "main",
    personalAccessToken: "",
    oauthConnected: false,
  },
  jira: { siteUrl: "", projectKeys: "", apiToken: "" },
};

export function isIntegrationConnected(
  id: IntegrationId,
  config: IntegrationConfigMap,
): boolean {
  switch (id) {
    case "slack":
      return Boolean(config.slack.botToken.trim());
    case "notion":
      return Boolean(config.notion.integrationToken.trim());
    case "github":
      return Boolean(
        config.github.repositoryUrl.trim() &&
          (config.github.personalAccessToken.trim() ||
            config.github.oauthConnected),
      );
    case "jira":
      return Boolean(
        config.jira.siteUrl.trim() && config.jira.apiToken.trim(),
      );
  }
}
