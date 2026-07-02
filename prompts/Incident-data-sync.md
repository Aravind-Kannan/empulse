# Prompt: End-to-End Incident Workspace Optimization & Cognee Memory Write-Back Loop

## Context
We are fully replacing the template-driven simulation in our Incident Investigation (II) workspace with live Cognee graph data. We must ensure that all 3 workspace panels function with authentic graph context and that any state changes (such as manual status updates) are written back to Cognee to update its long-term memory.

## Technical Tasks

### 1. Backend: Implement Multi-Hop Cognee Extraction & Graph Traversal
In `backend/app/services/investigation.py`, refactor `stream_investigation_chat()` and `build_diagnostics()` to replace `_SYSTEM_DIAGNOSTICS`:
* Use `await cognee.search()` with vector embeddings of the user's incident text to pull matching records across datasets (`tenant_id`).
* Traverse the extracted graph namespace to explicitly isolate:
  * Related **Notion / Postmortem** nodes to construct the probable root cause and workaround text strings.
  * Associated **Employee** handles linked via `ownsComponent` or Slack activity metrics to dynamically compute the `expertiseScore`.
  * Build a comprehensive string path representation of the traversed graph hops (e.g., `[Incident] -> [Auth-Service Component] -> [SarahDev Owner]`) for the UI trail.

### 2. Backend & Database: Complete the Memory Update Write-Back Loop
When a user modifies an incident status or leaves a follow-up resolution note, we must update both database layers:
* In `backend/app/routes/investigation.py`, inside the `PATCH /api/investigation/incidents/{id}` endpoint, after updating the PostgreSQL `IncidentRecord` row state:
  * Asynchronously invoke Cognee to update the memory layer:
    ```python
    # Update the status edge or attribute inside the Cognee graph context
    await cognee.add(
        data={
            "id": incident_id,
            "status": new_status,
            "updated_text": f"Incident status changed to {new_status}."
        }, 
        dataset_id=str(tenant_id)
    )
    await cognee.cognify(dataset_id=str(tenant_id))
    ```
  * This ensures future investigations can retrieve this historical incident as a "Resolved" reference case!

### 3. Frontend: Dynamic Binding of the 3-Panel State
* Open `frontend/src/components/investigation/InvestigationDiagnosticsPanel.tsx` and `InvestigationContextPanel.tsx`.
* Strip out any hardcoded template fallback indicators. Ensure that:
  * The **Center Panel** links the manual status dropdown directly to the optimized `PATCH` endpoint, showing a subtle loading indicator while Cognee re-indexes the graph state.
  * The **Right Panel** loops gracefully through the live references array (`slack_threads`, `jira_tickets`, `notion_pages`) passed down inside the SSE `type: diagnostics` chunk payload.
  * Sync frontend typing definitions explicitly within `frontend/src/lib/types.ts`.

Output the updated files for `backend/app/services/investigation.py`, `backend/app/routes/investigation.py`, and the modified frontend panels. Maintain clean multi-tenancy bounds.