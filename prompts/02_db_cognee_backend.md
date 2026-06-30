# Prompt 2: Database Schema & Cognee Graph Initialization
Context: The platform runs on a hybrid PostgreSQL operational layer and a Cognee knowledge graph memory layer.
Task: Code the data ingestion pipelines, mock schemas, and Cognee integration routines.

Requirements:
1. In `backend/app/config.py`, initialize Cognee layout setup parameters. Create a placeholder async utility to execute `cognee.add()` and `cognee.cognify()`.
2. Define a Pydantic user/org schema modeling Acme Company: 1 Manager, 4 Engineers, 1 Support.
3. Build backend data models representing:
   - Employee (id, name, role, email, tenure_years)
   - Component (id, name, description, open_tasks_count, unresolved_incidents)
   - Assignment / Knowledge Mapping (employee_id, component_id, codebase_share_pct)
4. Implement a POST route `/api/ingest/org-chart` that receives the validated JSON mapping from the frontend, uses Cognee to dynamically connect these entity nodes via custom edges (`reportsTo`, `manages`, `ownsComponent`), and persists operational attributes to PostgreSQL.
