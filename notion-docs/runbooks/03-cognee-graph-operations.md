# Runbook: Cognee & Graph Operations

**Owner:** Platform engineers  
**When:** Ingest failures, graph looks wrong, blast radius narrative empty

---

## Mental model

| Store | Role |
|-------|------|
| **Cognee graph** (Kuzu/Neo4j) | Relationships: owns, documents, contributes, depends |
| **LanceDB** | Vector embeddings for semantic search |
| **SQLite** (`cognee_db`) | Cognee metadata, dataset registry |
| **PostgreSQL** | Empulse operational data (not the graph) |

Per-tenant dataset: `empulse_tenant_{uuid-without-hyphens}`

---

## Ingest entry points

| Trigger | Service |
|---------|---------|
| Org chart | `cognee_ingest.py` via `POST /api/ingest/org-chart` |
| Integration sync | `integration_sync.py` → `run_cognee_add_and_cognify()` |
| Notion simulation | `notion_simulation.py`, graph debugger UI |
| ERA intelligence | `cognee_era_intelligence.py` |

Helper: `app/config.py` → `setup_cognee()` on app startup.

---

## Graph search (runtime)

```python
# Tenant-scoped — always use this, not raw cognee.search
tenant_graph_search(tenant, query, search_type=...)
```

Used by:

- KRA blast radius narrative (Metric 5)
- II investigation chat (best-effort)
- ERA backup candidate validation

**Cache:** KRA summary ~5 min; blast radius narrative ~1 h per component.

---

## Graph debugger UI

**Route:** `/settings/graph-debugger`

1. Enter Notion token + database ID (or use saved config)
2. Stream simulation progress
3. Inspect rendered graph nodes/edges

---

## Export graph as HTML

```bash
cd backend
python scripts/export_cognee_graph.py --tenant-id <TENANT_UUID> --open
```

Alternative to Neo4j Browser for visual inspection.

---

## Reset graph state (dev only)

```bash
# Stop backend first
rm -rf backend/.data_storage backend/.cognee_system backend/.cognee_cache
# Restart backend, re-run org chart ingest + integration sync
```

**Warning:** Destructive — all tenant graph data in local Cognee dirs is lost.

---

## Expected graph edges (by integration)

| Edge | Source |
|------|--------|
| `ownsComponent` | Assignments, CODEOWNERS |
| `contributedTo` | GitHub commits/PRs |
| `documentedBy` | Notion runbook pages |
| `dependsOn` | Component relations |
| `blocksComponent` | Jira issues |
| `resolvedOn` | Slack incident threads |

---

## LLM dependency

Cognee cognify and `GRAPH_COMPLETION` require Ollama:

```bash
curl http://localhost:11434/api/tags   # verify models loaded
```

If Ollama down:

- Deterministic metrics (KRA 1–4, ERA SQL scores) still work
- Blast radius narrative and II chat degrade gracefully

---

## Related

- [Tenant Neo4j inspection](./04-tenant-neo4j-inspection.md)
- Repo `backend/docs/neo4j-tenant-queries.md`
- ERA step 10: `design-docs/era/step-10-cognee-intelligence.md`
