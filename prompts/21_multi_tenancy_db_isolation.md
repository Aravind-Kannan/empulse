# Prompt 21: Database Multi-Tenancy Strategy & Cognee Graph Isolation
Context: To scale the platform for commercial or multi-org use, we must support strict multi-tenancy. Every database record, API call, and Cognee knowledge graph cluster must be isolated by a unique `tenant_id`.
Task: Implement backend multi-tenancy data isolation layers across PostgreSQL and Cognee.

Requirements:
1. **Tenant Model Setup:** Create a `Tenant` model (fields: `id`, `company_name`, `slug`, `created_at`).
2. **Schema Isolation Pass:**
   - Update all core operational tables in `backend/app/models/` (Employees, Teams, Components, Dynamic Roles, Incident Records, Identities) to include a foreign key column: `tenant_id = Column(UUID, ForeignKey('tenants.id'), nullable=False)`.
   - Implement an automated SQLAlchemy or FastAPI dependency function `get_current_tenant` that extracts the active `tenant_id` from a secure cookie or custom JWT claim header.
3. **Cognee Knowledge Graph Separation:**
   - Ensure all data documents sent via `cognee.add()` and indexed via `cognee.cognify()` are namespace-isolated using the user's `tenant_id`.
   - Prevent cross-tenant data leaks by configuring Cognee search, vector retrieval, and multi-hop graph queries to strictly scope traversals within the context of the active tenant namespace.