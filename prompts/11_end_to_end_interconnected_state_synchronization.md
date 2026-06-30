Context: Now that raw data from Slack, Notion, GitHub, and Jira converges inside Cognee, we must ensure these data points dynamically update our telemetry modules (ERA & KRA).
Task: Interlink the integration states with the primary analytical components.

Requirements:
1. Modify the **Employee Risk Assessment (ERA)** computation engine: Ingesting a backlog of unassigned high-priority bugs from Jira must instantly bump up the calculated `Risk Factor Score` for the components' main engineer.
2. Modify the **Knowledge Risk Assessment (KRA)** visualizer: Parsing complex code repositories via GitHub must automatically calculate codebase ownership splits. If GitHub shows only one engineer has pushed code to a specific directory path over the past 6 months, the KRA visual canvas must immediately mark that system module node as an alert-state Single Point of Failure (SPOF).
3. Verify that updating connection states inside the Integrations Hub cascades and refreshes all operational widgets and data tables across the parent workspace layout.