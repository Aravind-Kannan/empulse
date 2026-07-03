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
      "Add Bot Token Scopes: users:read, users:read.email, channels:read, groups:read, channels:history, groups:history, chat:write, im:write, files:write.",
      "If your workspace exposes org charts, enable users.profile:read for manager fields.",
      "Install the app to your workspace and copy the Bot User OAuth Token (xoxb-…).",
      "Paste your workspace URL (https://your-team.slack.com) and the bot token above.",
      "Empulse auto-discovers all channels the bot is a member of — invite the bot to any channel you want synced.",
      "Private channels require explicitly /invite-ing the bot; public channels may also need an invite depending on workspace settings.",
    ],
    docUrl: "https://api.slack.com/authentication/token-types#bot",
    docLabel: "Slack bot token docs",
  },
  github: {
    title: "How to get a GitHub personal access token",
    steps: [
      "Open GitHub → Settings → Developer settings → Personal access tokens.",
      "Generate a fine-grained token with repository read access, or a classic token with repo scope.",
      "Paste the token here and click Load accessible repositories.",
      "Select the repositories Empulse should sync, then choose all branches or a specific branch list.",
      "Empulse verifies access to each selected repository before syncing.",
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
      "Paste API token, then click Load accessible projects and select which to sync.",
      "Leave no projects selected to import all accessible projects.",
    ],
    docUrl: "https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/",
    docLabel: "Atlassian API token docs",
  },
};
