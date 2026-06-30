Context: Managers need a dedicated interface to manage third-party applications and connection configurations post-onboarding.
Task: Create an App-based Integrations Management page at `/settings/integrations` or `/integrations`.

Requirements:
1. Design an elegant, "App Store Style" grid grid system featuring service cards for **Slack**, **Notion**, **GitHub**, and **Jira**.
2. Each card must render its official logo styling, a brief description of what metadata it syncs to Cognee, an active status badge (`Connected`, `Disconnected`, `Syncing`), and a context action button ("Configure" or "Connect").
3. When clicking "Configure" on a disconnected app, open a specialized sidebar or modal overlay displaying the connection fields:
   - **GitHub:** Repository URL, Branch Targeting, Personal Access Token (PAT) or OAuth state.
   - **Jira:** Site Domain instance URL, Project Keys, and API Access Token.
4. Add a "Trigger Global Graph Sync" master action item at the top of the interface that shows an animated loading state tracking real-time ingestion across all connected sources.