# Runbook: Integration Sync

**Owner:** Platform / tenant admin  
**When:** After connecting a provider, on schedule, or when ERA/KRA metrics look stale

---

## Overview

```
Settings UI "Sync now"
        OR
POST /api/integrations/sync
POST /api/integrations/sync/{source}
        │
        ▼
integration_sync.py
        ├── github_client.py
        ├── jira_client.py
        ├── notion (via config)
        └── slack (via config)
        │
        ▼
Cognee ingest (tenant dataset)
        │
        ▼
integration_telemetry.py → ERA/KRA refresh
```

---

## Per-provider sync

| Source | Path | Prerequisites |
|--------|------|---------------|
| All | `POST /api/integrations/sync` | At least one connector configured |
| GitHub | `POST /api/integrations/sync/github` | PAT or app creds in tenant config |
| Jira | `POST /api/integrations/sync/jira` | Site URL + API token |
| Notion | `POST /api/integrations/sync/notion` | Integration token + database IDs |
| Slack | `POST /api/integrations/sync/slack` | Bot token + workspace |

Requires authenticated tenant context (cookie or `X-Tenant-ID`).

---

## Post-sync verification

| Check | How |
|-------|-----|
| Graph updated | `/settings/graph-debugger` or Neo4j queries |
| ERA scores changed | `/era` — check `computed_at` |
| KRA SPOF count | `/kra` summary strip |
| Unmapped activity | ERA unmapped banner — reconcile identity |
| Telemetry snapshots | PostgreSQL tables: `github_ownership_snapshots`, `notion_doc_snapshots`, etc. |

---

## Identity reconciliation

**Symptom:** Sync succeeds but ERA shows unmapped banner.

**Steps:**

1. Open Settings → Identity mappings
2. Match provider user IDs to employees
3. `PUT /api/identity/mappings` for each link
4. Re-run sync for affected provider

**Rule:** Never manually attribute quarantined events without confirmed mapping.

---

## Common issues

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 401 from GitHub/Jira | Expired token | Rotate in Settings |
| Empty graph after sync | Wrong repo/project scope | Check integration config |
| Partial KRA badges | Missing Notion or GitHub | Connect missing provider |
| Duplicate employees | Email mismatch | Normalize in Notion directory |
| Slow sync | Large repo | Sync single source; increase timeout |

---

## Manual Notion → Cognee test

```bash
cd backend
python scripts/test_notion_cognee.py \
  --notion-token "$NOTION_INTEGRATION_TOKEN" \
  --notion-database-id "$NOTION_DATABASE_ID"
```

---

## Demo vs live data

| Mode | Indicator |
|------|-----------|
| `demo_mode` tenant | UI labels; synthetic telemetry |
| Live connectors | Real API responses in snapshots |

Handover and ERA exports include demo preamble when applicable.

---

## Related

- [Integrations design](../design/06-integrations-platform.md)
- [Cognee operations](./03-cognee-graph-operations.md)
- [Troubleshooting](./05-troubleshooting.md)
