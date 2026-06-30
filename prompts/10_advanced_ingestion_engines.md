Context: To fuel the ERA, KRA, and Incident Investigation workflows with live data, our FastAPI backend must process structured artifacts from GitHub and Jira and transform them into semantic Graph vectors via Cognee.
Task: Develop the backend schema extensions, mock data feeds, and Cognee processing logic for GitHub and Jira.

Requirements:
1. Create a backend router module at `backend/app/routes/integrations.py` to handle configuration submission and manual sync requests for GitHub and Jira.
2. Extend the Cognee ingestion logic. Code a mock document analyzer that acts on:
   - **GitHub Payloads:** Commits data, PR numbers, file diff pathways, and structural line changes (`LOC`). Map these entities to existing Employee nodes via `contributedTo` or `modifies` graph edges.
   - **Jira Payloads:** Ticket IDs, issue types (Bug, Task), priority levels, assigned engineering contacts, and status indicators. Link these using `blocksComponent` or `assignedTo` graph edges.
3. Write an asynchronous execution utility `async def process_external_app_sync(source: str)` that transforms raw app data strings, calls `cognee.add()` to load them, and executes `cognee.cognify()` to update the underlying Multi-hop Knowledge Graph.
4. Connect this pipeline seamlessly to the frontend configuration buttons built in the previous prompt.