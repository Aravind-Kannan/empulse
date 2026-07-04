# KRA — Knowledge Risk Assessment

**Route:** `/kra`  
**Audience:** Engineering managers, staff engineers, platform leads

System-centric **structural risk**: where is knowledge trapped, and what breaks if a critical owner leaves? Complements ERA (person-centric). Built from org-chart assignments, GitHub/Notion/Jira/Slack telemetry, and the tenant Cognee graph.

## Capabilities

- Component graph with owners and dependencies
- KPI strip: critical SPOFs, documentation coverage, incident knowledge debt, backup readiness
- Component detail drawer with blast-radius narrative (Cognee)
- File risk matrix and deep links from ERA SPOF KPI

## Mapped source paths

GitHub blame, PR reviews, and code ingest on these paths attribute to the **Kra** component during integration sync.

- `backend/app/services/kra_analytics.py`
- `backend/app/services/kra_metrics.py`
- `backend/app/schemas/kra.py`
- `backend/tests/test_kra_documentation_coverage.py`
- `backend/tests/test_kra_ownership.py`
- `backend/tests/test_kra_spof_reasons.py`
- `backend/tests/test_kra_critical_spof.py`
- `frontend/src/components/kra/`
- `frontend/src/app/kra/`
- `frontend/src/components/landing/BentoKraAlerts.tsx`
- `notion-docs/design/02-kra.md`
- `prompts/kra/`

## Identity & sync notes

KRA metrics are **component-first** — owners and backups come from org-chart assignments plus GitHub blame/PR attribution. Contributors must be mapped in identity settings for accurate bus-factor and backup readiness.

| Signal | Provider | Used for |
|--------|----------|----------|
| Blame / PR author | GitHub | Owner activity, bus factor |
| Assignee on incidents | Jira | Incident knowledge debt |
| Page editors | Notion | Documentation coverage |
| Thread participants | Slack | Incident resolution context |

Re-run **Integration sync** after updating assignments or identity mappings.

## Related

- [ERA](../era/README.md) — person-centric risk; SPOF KPI links here
- [Identity Mapping](../identity-mapping/README.md)
- [Integration Sync](../integration-sync/README.md)
- [KRA design spec](../../notion-docs/design/02-kra.md)
