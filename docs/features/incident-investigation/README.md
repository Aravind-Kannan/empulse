# Incident Investigation (II)

**Route:** `/investigation`  
**Audience:** On-call engineers, engineering managers

Three-panel workspace for incident triage: timeline, diagnostics (Jira/GitHub/Slack/Notion), and streaming AI chat grounded in the tenant Cognee graph.

## Capabilities

- Incident list and lifecycle updates
- Cross-source diagnostics and reference links
- Streaming investigation chat
- Component matching from incident text and corpus

## Mapped source paths

- `backend/app/services/investigation.py`
- `backend/app/routes/investigation.py`
- `backend/app/schemas/investigation.py`
- `backend/docs/incident-investigation-current.md`
- `backend/tests/test_investigation_references.py`
- `backend/tests/test_investigation_jira_diagnostics.py`
- `backend/tests/test_incident_investigation_related.py`
- `frontend/src/components/investigation/`
- `frontend/src/app/investigation/`
- `frontend/src/hooks/useIncidentInvestigation.ts`
- `notion-docs/design/03-incident-investigation.md`
- `prompts/06_incident_investigation_workspace.md`

## Identity & sync notes

Diagnostics surface **assignees and authors** from Jira issues and GitHub activity. Those provider ids must be mapped to employees for person-centric rollups in ERA and accurate component ownership in KRA.

| Source | Typical id |
|--------|------------|
| Jira assignee | Atlassian `accountId` |
| GitHub commit/PR | `gh-{login}` |
| Slack thread | Slack user id |

## Related

- [Integration Sync](../integration-sync/README.md)
- [Identity Mapping](../identity-mapping/README.md)
