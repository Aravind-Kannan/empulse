# Integrations & Platform

**Route:** `/settings`  
**Audience:** Platform engineers, tenant admins

---

## Supported integrations

| Provider | Data ingested | Graph edges | Powers |
|----------|---------------|-------------|--------|
| **GitHub** | Commits, PRs, CODEOWNERS, reviews | `contributedTo`, `modifies`, `reviews` | ERA K, KRA 1/2/4, DOA, file risk |
| **Jira** | Issues, epics, assignees, priorities | `blocksComponent`, `assignedTo` | ERA O, KRA 3/5, II gate |
| **Notion** | People DB, runbooks, component pages | `documentedBy`, org relations | ERA D/K/S, KRA 2/3 |
| **Slack** | Users, incident threads, on-call | `resolvedOn`, identity | ERA O/D/B, KRA 3 |

---

## Sync pipeline

```
POST /api/integrations/sync          → global sync (all connected)
POST /api/integrations/sync/{source} → single source (github|jira|notion|slack)
        │
        ▼
integration_sync.py → provider clients → Cognee ingest
        │
        ▼
integration_telemetry.py → ERA/KRA metric refresh
```

Entry points:

- Settings UI "Sync now" button
- Onboarding wizard post-connect
- Scheduled sync (future)

---

## Identity mapping

All telemetry joins flow through **employee identity resolution**:

| Confidence | Rule |
|------------|------|
| `confirmed` | User saved via `PUT /api/identity/mappings` |
| `high` | Email exact match |
| `medium` | Fuzzy name match (+ warning flag) |
| `none` | → `UnmappedActivity` quarantine queue |

**Rule:** Unmapped activity is never attributed to a guessed employee.

API prefix: `/api/identity`

---

## Tenant configuration

| Store | Scope |
|-------|-------|
| PostgreSQL `tenant_integration_configs` | Per-tenant connector credentials/settings |
| Cognee dataset | `empulse_tenant_{uuid-no-hyphens}` |
| localStorage (frontend) | UI integration status cache |

---

## Graph debugger

**Route:** `/settings/graph-debugger`

- Streams Notion → Cognee simulation
- Renders resulting knowledge graph
- Useful for validating ingest before live connectors

Script alternative:

```bash
cd backend
python scripts/test_notion_cognee.py \
  --notion-token "$NOTION_INTEGRATION_TOKEN" \
  --notion-database-id "$NOTION_DATABASE_ID"
```

---

## Workspace integration gates

Some modules require specific connectors (see `frontend/src/lib/integrations.ts`):

| Module | Required |
|--------|----------|
| Incident Investigation | Jira validated |
| KRA (full metrics) | GitHub recommended |
| ERA (full scoring) | At least one telemetry source + identity map |

Missing integrations show **partial** badges — never fake zero scores.

---

## Environment variables (backend)

Key vars in `backend/.env.example`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection |
| `COGNEE_DATASET_NAME` | Default dataset name |
| Ollama settings | LLM + embeddings for Cognee |
| Provider tokens | GitHub, Jira, Notion, Slack (per-tenant override in DB) |
| `ENABLE_BACKEND_ACCESS_CONTROL` | Neo4j dedicated DB per tenant |
| `INTERNAL_DEBUG_KEY` | Internal tenant/Neo4j debug endpoints |

---

## Demo mode

`demo_mode` flag (tenant-level) distinguishes simulated telemetry from live connector data. UI must label demo data clearly; handover and ERA exports include preamble warning.

---

## Related

- [Runbook: integration sync](../runbooks/02-integration-sync.md)
- [Runbook: Cognee operations](../runbooks/03-cognee-graph-operations.md)
- [Runbook: tenant Neo4j](../runbooks/04-tenant-neo4j-inspection.md)
- ERA step docs: 04–07 (per-connector telemetry)
