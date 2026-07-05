import {
  githubRepoSyncBranchLabel,
  parseJiraProjectKeys,
  type IntegrationConfigMap,
  type IntegrationId,
} from "@/lib/integrations";

export interface IntegrationSummaryRow {
  label: string;
  value: string;
}

export function integrationConfigSummary(
  id: IntegrationId,
  config: IntegrationConfigMap,
): IntegrationSummaryRow[] {
  switch (id) {
    case "slack": {
      const rows: IntegrationSummaryRow[] = [];
      if (config.slack.workspaceUrl.trim()) {
        rows.push({ label: "Workspace", value: config.slack.workspaceUrl.trim() });
      }
      if (config.slack.channelIds.trim()) {
        rows.push({
          label: "Channels",
          value: config.slack.channelIds.trim(),
        });
      } else {
        rows.push({ label: "Channels", value: "Auto-discover all joined channels" });
      }
      rows.push({
        label: "Credentials",
        value: config.slack.botToken.trim() ? "Bot token configured" : "Not set",
      });
      return rows;
    }
    case "notion": {
      const rows: IntegrationSummaryRow[] = [];
      if (config.notion.databaseIds.trim()) {
        rows.push({
          label: "Databases",
          value: config.notion.databaseIds.trim(),
        });
      } else {
        rows.push({
          label: "Databases",
          value: "Auto-discover all shared databases",
        });
      }
      rows.push({
        label: "Credentials",
        value: config.notion.integrationToken.trim()
          ? "Integration token configured"
          : "Not set",
      });
      return rows;
    }
    case "github": {
      const repos =
        config.github.repositoryUrls.length > 0
          ? config.github.repositoryUrls
          : config.github.repositoryUrl.trim()
            ? [config.github.repositoryUrl.trim()]
            : [];
      const rows: IntegrationSummaryRow[] = [];
      rows.push({
        label: "Repositories",
        value:
          repos.length > 0
            ? `${repos.length} selected`
            : "None selected",
      });
      if (repos.length > 0 && repos.length <= 3) {
        rows.push({
          label: "Repo list",
          value: repos.map(shortRepoLabel).join(", "),
        });
      }
      rows.push({
        label: "Branch scope",
        value: githubRepoSyncBranchLabel(config.github),
      });
      rows.push({
        label: "File content",
        value: config.github.ingestFileContent
          ? "Full file bodies & diff patches"
          : "Metadata only (paths, blame, commits)",
      });
      rows.push({
        label: "Credentials",
        value:
          config.github.personalAccessToken.trim() || config.github.oauthConnected
            ? "Access token configured"
            : "Not set",
      });
      return rows;
    }
    case "jira": {
      const keys = parseJiraProjectKeys(config.jira.projectKeys);
      const rows: IntegrationSummaryRow[] = [];
      if (config.jira.siteUrl.trim()) {
        rows.push({ label: "Site", value: config.jira.siteUrl.trim() });
      }
      if (config.jira.authEmail.trim()) {
        rows.push({ label: "Account", value: config.jira.authEmail.trim() });
      }
      rows.push({
        label: "Projects",
        value:
          keys.length > 0
            ? keys.join(", ")
            : "All accessible projects",
      });
      rows.push({
        label: "Credentials",
        value: config.jira.apiToken.trim() ? "API token configured" : "Not set",
      });
      return rows;
    }
  }
}

const LIST_CARD_CAPABILITY_CHIPS: Record<IntegrationId, string[]> = {
  slack: ["Org roster", "ERA & Exit", "90-day lookback"],
  notion: ["Org roster", "ERA & Exit", "Documentation"],
  github: ["Org roster", "ERA, Exit & KRA", "Repos & PRs"],
  jira: ["Org roster", "ERA & Exit", "Investigation"],
};

/** Short scope + capability chips for integrations directory cards. */
export function integrationListCardChips(
  id: IntegrationId,
  config: IntegrationConfigMap,
  connected: boolean,
): string[] {
  const chips: string[] = [];

  if (connected) {
    switch (id) {
      case "slack":
        chips.push(
          config.slack.channelIds.trim() ? "Selected channels" : "All joined channels",
        );
        break;
      case "notion":
        chips.push(
          config.notion.databaseIds.trim() ? "Selected databases" : "All shared databases",
        );
        break;
      case "github": {
        const repos =
          config.github.repositoryUrls.length > 0
            ? config.github.repositoryUrls
            : config.github.repositoryUrl.trim()
              ? [config.github.repositoryUrl.trim()]
              : [];
        if (repos.length > 0) {
          chips.push(`${repos.length} repo${repos.length === 1 ? "" : "s"}`);
        }
        chips.push(
          config.github.ingestFileContent ? "Full file content" : "Metadata only",
        );
        break;
      }
      case "jira": {
        const keys = parseJiraProjectKeys(config.jira.projectKeys);
        chips.push(
          keys.length > 0
            ? `${keys.length} project${keys.length === 1 ? "" : "s"}`
            : "All projects",
        );
        break;
      }
    }
  }

  for (const chip of LIST_CARD_CAPABILITY_CHIPS[id] ?? []) {
    if (chips.length >= 3) break;
    if (!chips.includes(chip)) chips.push(chip);
  }

  return chips.slice(0, 3);
}

function shortRepoLabel(url: string): string {
  try {
    const parts = new URL(url).pathname.split("/").filter(Boolean);
    if (parts.length >= 2) {
      return `${parts[0]}/${parts[1]}`;
    }
  } catch {
    // fall through
  }
  return url.replace(/^https?:\/\//, "");
}
