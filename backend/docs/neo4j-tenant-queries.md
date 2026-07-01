# Neo4j tenant queries (Empulse + Cognee)

Reference for inspecting one tenant's graph in Neo4j Browser and understanding isolation with a shared Neo4j instance.

## Prerequisites

- Neo4j running: `docker compose up -d neo4j`
- Browser: http://localhost:7474
- Default credentials (from `.env`): `neo4j` / `pleaseletmein`
- Bolt URL: `bolt://localhost:7687`

## Tenant naming

| Concept | Rule | Example |
|---------|------|---------|
| Cognee dataset | `empulse_tenant_{uuid-without-hyphens}` | `empulse_tenant_00000000000040008000000000000001` |
| Employee ID prefix | `emp-{first-8-hex-of-uuid}-` | `emp-00000000-alice` |
| Component ID prefix | `comp-{first-8-hex-of-uuid}-` | `comp-00000000-api` |
| Default bootstrap tenant UUID | fixed | `00000000-0000-4000-8000-000000000001` |

## Get connection details via API

```bash
# Current tenant (requires tenant cookie or X-Tenant-ID)
curl -s http://localhost:8000/api/internal/tenants/current/neo4j-access \
  -H "X-Tenant-ID: <TENANT_UUID>" | jq

# Specific tenant
curl -s http://localhost:8000/api/internal/tenants/<TENANT_UUID>/neo4j-access | jq
```

Optional header if `INTERNAL_DEBUG_KEY` is set in `.env`:

```bash
-H "X-Internal-Debug-Key: <your-key>"
```

Response fields to use:

- `cognee_dataset_name` — filter for shared-DB queries
- `neo4j.database` — dedicated DB name (or `neo4j` when shared)
- `neo4j.startup_commands` — e.g. `:use cognee…`
- `neo4j.browser_url`, `neo4j.bolt_url`, credentials

---

## Mode A: Dedicated Neo4j DB per tenant

Requires `ENABLE_BACKEND_ACCESS_CONTROL=true` and **Neo4j Enterprise**.

In Neo4j Browser, select the tenant database (from internal endpoint `neo4j.database`):

```cypher
:use cognee5c5ad1054fbc55f8b09c6997218684b0
```

All nodes in that database belong to one tenant:

```cypher
MATCH (n)
RETURN n
LIMIT 100;
```

With relationships:

```cypher
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100;
```

---

## Mode B: Shared Neo4j DB (current default)

`ENABLE_BACKEND_ACCESS_CONTROL=false` — all tenants share the `neo4j` database.

Cognee stores nodes with label `__Node__`. Dataset membership is on `belongs_to_set` (for cognify/search nodes).

### Filter by Cognee dataset (preferred)

```cypher
:param datasetName => 'empulse_tenant_00000000000040008000000000000001';

MATCH (n:`__Node__`)
WHERE $datasetName IN coalesce(n.belongs_to_set, [])
RETURN n
LIMIT 100;
```

Graph view:

```cypher
:param datasetName => 'empulse_tenant_00000000000040008000000000000001';

MATCH (n:`__Node__`)-[r]->(m:`__Node__`)
WHERE $datasetName IN coalesce(n.belongs_to_set, [])
  AND $datasetName IN coalesce(m.belongs_to_set, [])
RETURN n, r, m
LIMIT 100;
```

### Fallback: Empulse org-chart nodes (structured ingest)

Org ingest writes tenant-prefixed `external_id` values. For tenant `00000000-0000-4000-8000-000000000001`:

```cypher
MATCH (n:`__Node__`)
WHERE n.external_id STARTS WITH 'emp-00000000-'
   OR n.external_id STARTS WITH 'comp-00000000-'
RETURN n
LIMIT 100;
```

Generalize: replace `00000000` with the first 8 hex characters of the tenant UUID (no hyphens).

### Count nodes per dataset (debug)

```cypher
MATCH (n:`__Node__`)
UNWIND coalesce(n.belongs_to_set, []) AS dataset
RETURN dataset, count(*) AS nodes
ORDER BY nodes DESC;
```

---

## Isolation summary

| Store | Shared DB mode | Dedicated DB mode |
|-------|----------------|-------------------|
| **Neo4j (graph)** | One `neo4j` DB; filter in Cypher or use API dataset scope | One DB per tenant dataset |
| **LanceDB (vectors)** | Shared index; search filtered by dataset name | Per-tenant LanceDB files |
| **SQLite (Cognee metadata)** | Always shared `cognee_db`; rows keyed by dataset | Same |
| **PostgreSQL (Empulse)** | Always isolated by `tenant_id` | Same |

**Empulse API queries** (`tenant_graph_search`, ingest with `datasets=[…]`) are scoped to the active tenant's Cognee dataset. **Raw Neo4j Browser queries** on the shared `neo4j` database can see all tenants unless you use the filters above.

To enable physical graph isolation: set `ENABLE_BACKEND_ACCESS_CONTROL=true` and use `neo4j:5-enterprise` in `docker-compose.yml`.

---

## Export graph as HTML (alternative to Browser)

```bash
cd backend
python scripts/export_cognee_graph.py --tenant-id <TENANT_UUID> --open
```
