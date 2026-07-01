# Prompt: Implement Jira Integration and Ingestion Pipeline (Dual-DB with Cognee)

Context: We are expanding the Empulse engineering intelligence suite by adding a Jira Integration module. This must follow our hybrid architecture: PostgreSQL tracks the secure operational configuration and metadata states, while Cognee digests raw text streams to expand our knowledge graph connections.

Task: Build the structural database definitions, validation schemas, API routing, and Cognee background service pipelines.

Requirements:

1. Database Layer (PostgreSQL)
- In `backend/app/models/`, create a `JiraIntegration` model containing:
  - id (UUID, PK), tenant_id (UUID, FK to tenants), jira_domain (String), auth_email (String), encrypted_api_token (String), status (String), last_synced_at (DateTime, Nullable).
- Enforce multi-tenancy rules matching existing repository patterns.

2. Validation Schemas
- Create `backend/app/schemas/jira.py`:
  - `JiraConnectRequest`: Validates jira_domain, auth_email, encrypted_api_token, and project_keys.
  - `JiraIntegrationResponse`: Outputs configuration metrics securely (hiding sensitive keys).

3. Ingestion & Telemetry Service
- Create `backend/app/services/jira_service.py` featuring an async function `sync_jira_to_cognee(tenant_id: UUID)`:
  - Mock a payload stream of engineering issues (Bugs, Tasks, Epics) including descriptions that reference key infrastructure pieces (e.g., "Task: Migrate database pools inside the authentication-service. Assignee: @SarahDev").
  - Append raw documents/strings using `await cognee.add(data=payload, dataset_id=str(tenant_id))`.
  - Process structural context nodes using `await cognee.cognify(dataset_id=str(tenant_id))`.
  - Track live stage progression diagnostics in `backend/data/jira_debug_state.json` matching our established debugging panel architectures (Stages: Fetching Issues, Sanitizing Metadata, Vector Append, Graph Cognify).

4. FastAPI Routes
- Create `backend/app/routes/jira.py` mapped to the principal application router tree:
  - `GET /api/integrations/jira`: Reads verification state and history metrics.
  - `POST /api/integrations/jira/connect`: Captures credentials, instantiates a database row, shifts operational state to 'syncing', and initializes the background Cognee routine.
- Protect all end points behind the native multi-tenant verification filters.

Output complete, clean, modular Python source code files only.