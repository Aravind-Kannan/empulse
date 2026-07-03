# Runbook: Tenant & Neo4j Inspection

**Owner:** Platform engineers  
**When:** Debug cross-tenant leakage, verify ingest, inspect graph manually

> **Full Cypher reference:** Repo `backend/docs/neo4j-tenant-queries.md`

---

## Prerequisites

```bash
docker compose up -d neo4j
```

| Item | Value |
|------|-------|
| Browser | http://localhost:7474 |
| Bolt | `bolt://localhost:7687` |
| Default creds | `neo4j` / `pleaseletmein` (from `.env`) |

---

## Tenant naming

| Concept | Pattern | Example |
|---------|---------|---------|
| Cognee dataset | `empulse_tenant_{uuid-no-hyphens}` | `empulse_tenant_00000000000040008000000000000001` |
| Employee ID | `emp-{first-8-hex}-` | `emp-00000000-alice` |
| Component ID | `comp-{first-8-hex}-` | `comp-00000000-api` |
| Dev bootstrap UUID | fixed | `00000000-0000-4000-8000-000000000001` |

---

## Get connection details via API

```bash
curl -s http://localhost:8000/api/internal/tenants/current/neo4j-access \
  -H "X-Tenant-ID: <TENANT_UUID>" | jq
```

Optional if `INTERNAL_DEBUG_KEY` set:

```bash
-H "X-Internal-Debug-Key: <your-key>"
```

Response fields: `cognee_dataset_name`, `neo4j.database`, `neo4j.startup_commands`, credentials.

---

## Mode A: Dedicated DB per tenant

Requires `ENABLE_BACKEND_ACCESS_CONTROL=true` + Neo4j Enterprise.

```cypher
:use cognee5c5ad1054fbc55f8b09c6997218684b0

MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100;
```

---

## Mode B: Shared DB (default)

`ENABLE_BACKEND_ACCESS_CONTROL=false` — filter by dataset:

```cypher
:param datasetName => 'empulse_tenant_00000000000040008000000000000001';

MATCH (n:`__Node__`)-[r]->(m:`__Node__`)
WHERE $datasetName IN coalesce(n.belongs_to_set, [])
  AND $datasetName IN coalesce(m.belongs_to_set, [])
RETURN n, r, m
LIMIT 100;
```

### Fallback: org-chart prefix filter

```cypher
MATCH (n:`__Node__`)
WHERE n.external_id STARTS WITH 'emp-00000000-'
   OR n.external_id STARTS WITH 'comp-00000000-'
RETURN n
LIMIT 100;
```

Replace `00000000` with first 8 hex chars of tenant UUID.

### Count nodes per dataset

```cypher
MATCH (n:`__Node__`)
UNWIND coalesce(n.belongs_to_set, []) AS dataset
RETURN dataset, count(*) AS nodes
ORDER BY nodes DESC;
```

---

## Isolation summary

| Store | Shared mode | Dedicated mode |
|-------|-------------|----------------|
| Neo4j | One DB; filter in Cypher | One DB per tenant |
| LanceDB | Shared index; filtered by dataset | Per-tenant files |
| PostgreSQL | Always `tenant_id` scoped | Same |

**Important:** Empulse API queries are tenant-scoped. Raw Neo4j Browser on shared `neo4j` DB can see all tenants without filters.

---

## Enable physical graph isolation

1. Set `ENABLE_BACKEND_ACCESS_CONTROL=true` in `.env`
2. Use `neo4j:5-enterprise` in `docker-compose.yml`
3. Restart stack

---

## Related

- [Cognee operations](./03-cognee-graph-operations.md)
- [Troubleshooting](./05-troubleshooting.md)
