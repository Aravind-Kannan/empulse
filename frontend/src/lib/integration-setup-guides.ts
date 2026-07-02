import type { IntegrationId } from "@/lib/integrations";

export interface IntegrationSetupGuide {
  title: string;
  steps: string[];
  docUrl?: string;
  docLabel?: string;
}

export const INTEGRATION_SETUP_GUIDES: Record<
  IntegrationId,
  IntegrationSetupGuide
> = {
  notion: {
    title: "How to get your Notion integration token",
    steps: [
      "Open notion.so/my-integrations and click + New integration.",
      "Name it (e.g. Empulse) and select the workspace to connect.",
      "Under Capabilities, enable Read content (and Update if you plan to write back).",
      "Copy the Internal Integration Secret — it starts with secret_ or ntn_.",
      "Share the pages and databases you want imported with the integration (••• → Connect to).",
      "Empulse auto-discovers all accessible databases and pages — no manual IDs required.",
      "Optional: add database IDs below to limit import to specific sources.",
    ],
    docUrl: "https://developers.notion.com/docs/create-a-notion-integration",
    docLabel: "Notion integration docs",
  },
  slack: {
    title: "How to get your Slack bot token",
    steps: [
      "Go to api.slack.com/apps and create a new app (From scratch).",
      "Choose your workspace, then open OAuth & Permissions.",
      "Add Bot Token Scopes: users:read, users:read.email, channels:read (minimum).",
      "If your workspace exposes org charts, enable users.profile:read for manager fields.",
      "Install the app to your workspace and copy the Bot User OAuth Token (xoxb-…).",
      "Paste your workspace URL (https://your-team.slack.com) and the bot token above.",
      "Optional: add channel IDs (right-click channel → View channel details → copy ID).",
    ],
    docUrl: "https://api.slack.com/authentication/token-types#bot",
    docLabel: "Slack bot token docs",
  },
  github: {
    title: "How to get a GitHub personal access token",
    steps: [
      "Open GitHub → Settings → Developer settings → Personal access tokens.",
      "Generate a fine-grained token scoped to your repository, or a classic token with repo read access.",
      "Fine-grained tokens must explicitly include the repository URL you enter below.",
      "Paste the repository URL, target branch, and token here — Empulse verifies access before syncing.",
    ],
    docUrl: "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
    docLabel: "GitHub PAT docs",
  },
  jira: {
    title: "How to get a Jira API token",
    steps: [
      "Log in at id.atlassian.com/manage-profile/security/api-tokens.",
      "Create API token and copy the value (starts with ATATT…).",
      "Enter your Jira Cloud site URL (https://your-org.atlassian.net).",
      "Enter the Atlassian account email paired with your API token.",
      "Optional: list project keys to sync (e.g. ENG, PLAT). Leave empty to import all projects.",
    ],
    docUrl: "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
    docLabel: "Atlassian API token docs",
  },
};
