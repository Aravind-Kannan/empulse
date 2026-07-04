# ERA — Employee Risk Assessment

**Route:** `/era`  
**Audience:** Engineering managers, HR business partners

Person-centric **continuity risk**: if this employee left tomorrow, how much operational and knowledge risk does the org take? Built from GitHub, Jira, Slack, Notion, and org-chart signals via identity mapping and Cognee.

## Capabilities

- Team risk command center, heatmap, KPI strip
- Per-employee dimension scores (K / O / D / S / B)
- Evidence feed, file hotspots, review network
- Proactive alerts and review cadence
- Bridge to Employee Knowledge Handover

## Mapped source paths

GitHub blame, PR reviews, and code ingest on these paths attribute to the **Era** component during integration sync.

- `backend/app/services/era/`
- `backend/app/services/era_analytics.py`
- `backend/app/services/era_alerts.py`
- `backend/app/services/era_snapshots.py`
- `backend/app/services/era_settings_store.py`
- `backend/app/services/cognee_era_intelligence.py`
- `backend/app/routes/analytics.py`
- `backend/tests/test_era_alerts.py`
- `frontend/src/components/era/`
- `frontend/src/app/era/`
- `design-docs/era/`
- `notion-docs/design/01-era.md`
- `notion-docs/runbooks/06-era-review-cadence.md`

## Identity & sync notes

| Signal | Provider | Resolution |
|--------|----------|------------|
| PR author, blame lines | GitHub | `gh-{login}` → employee via identity mapping |
| Assignee, reporter | Jira | `accountId` → employee |
| Thread author | Slack | `U…` user id → employee |
| Page editor | Notion | workspace user → employee |

Re-run **Integration sync** after saving identity mappings so historical quarantine can reconcile.

## Related

- [KRA](../kra/README.md) — system-centric SPOF and doc coverage
- [Employee Knowledge Handover](../employee-exit/README.md)
- [Identity Mapping](../identity-mapping/README.md)
- [Integration Sync](../integration-sync/README.md)
