# KRA Metric 3 — Incident Knowledge Debt

> **Prerequisite:** Prompts 1–2 complete.  
> **Sequence:** Prompt 3 of 5 — closes II → runbook learning loop.

## Context

KRA Metric 3 closes the loop between **Incident Investigation (II)** and knowledge capture:

> **Are we learning from incidents or repeating them?**

A component with repeat incidents but no post-incident doc update = **incident knowledge debt** — tacit fixes stay in Slack threads, not runbooks.

**Scoring:** deterministic multi-hop check across Slack/Jira telemetry + Notion doc freshness. Cognee graph path: `SlackIncident → component → documentedBy → NotionPage`.

## What exists today

| Area | Location | Notes |
|------|----------|-------|
| Slack incident threads | `integration_telemetry` — `get_cached_slack_threads()`, thread cache in telemetry | Serialized on sync |
| Jira incidents | `get_cached_jira_issues()` — bug/incident types | Component mapping via `component_id` |
| Incident feed | `backend/app/services/incident_feed.py` | Builds incident cards from telemetry |
| Investigation | `backend/app/services/investigation.py` | Cognee root-cause / solutions search |
| Design reference | `design-docs/era/step-10-cognee-intelligence.md` | `GraphSlackIncident` node (optional) |

## Task

Implement **Incident Knowledge Debt** count: components with ≥2 incidents in 90 days and no `documentedBy` update within 30 days of the **last** incident.

---

## Product definition

| Field | Value |
|-------|-------|
| **Display label** | Incident knowledge debt |
| **Headline** | `{n} systems had repeat incidents without doc updates` |
| **Severity** | Amber if n > 0 |
| **Click action** | List debt components with incident links (Slack thread URL, Jira key) |

### Definitions

| Term | Rule |
|------|------|
| **Incident event** | Slack thread in incident/on-call channel (`is_incident_channel` or `is_on_call_channel`) resolved in last 90d **OR** open/done Jira bug with `is_bug_or_incident` mapped to component |
| **Repeat** | ≥2 distinct incident events on same `component_id` in 90d window |
| **Doc updated** | Notion page linked via `documentedBy` / `get_notion_component_sources` edited within 30 days **after** `last_incident_at` |
| **In debt** | Repeat **and** doc not updated in that window |

### Formula

```python
for component_id in components_with_incidents:
    events = incidents_for_component(component_id, window_days=90)
    if len(events) < 2:
        continue
    last_incident_at = max(e.resolved_at or e.updated_at for e in events)
    last_doc_edit = latest_notion_edit(component_id)
    if last_doc_edit is None or last_doc_edit < last_incident_at + timedelta(days=30):
        debt_components.append(...)
```

Org metric = `len(debt_components)`.

---

## Backend requirements

### 1. Service function

In `backend/app/services/kra_metrics.py`:

```python
def compute_incident_knowledge_debt(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    incident_window_days: int = 90,
    doc_grace_days: int = 30,
) -> IncidentKnowledgeDebtResult:
    ...
```

```python
class IncidentDebtEvent(BaseModel):
    source: Literal["slack", "jira"]
    label: str                    # e.g. "#incidents thread" or "PROJ-123"
    url: str | None
    occurred_at: str              # ISO

class IncidentDebtComponent(BaseModel):
    component_id: str
    component_name: str
    incident_count: int
    last_incident_at: str
    last_doc_edit: str | None
    events: list[IncidentDebtEvent]   # max 5 for UI

class IncidentKnowledgeDebtResult(BaseModel):
    count: int
    components: list[IncidentDebtComponent]
    data_completeness: KraMetricCoverage
```

### 2. Data sources (priority order)

1. **Telemetry cache** (fast): `get_cached_slack_threads()`, `get_cached_jira_issues()` after `hydrate_integration_telemetry`
2. **SQL**: `NotionDocSnapshot.last_edited` per component
3. **Cognee graph** (optional enrichment): verify `SlackIncident → component` edges if ingested

Do **not** call Slack/Jira live APIs on summary load.

### 3. Cognee ingest (optional enhancement)

If not present, add during Slack sync in `integration_sync.py`:

```python
class GraphSlackIncident(DataPoint):
    thread_id: str
    channel_name: str
    resolved_at: str
    component: GraphComponent | None
```

Edge: `GraphSlackIncident → resolvedOn → GraphComponent`

Summary metric still uses telemetry; graph enables richer drill-down in investigation workspace.

### 4. API

Extend `GET /api/analytics/kra/summary`:

```json
{
  "incident_knowledge_debt": {
    "count": 4,
    "components": [...],
    "data_completeness": { "slack": "confirmed", "jira": "high", "notion": "confirmed" }
  }
}
```

### 5. Cross-link to Investigation

Debt components should be linkable from II briefing context:

- Add `knowledge_debt_flag: bool` on component metadata in investigation diagnostics (optional follow-up — stub OK)

### 6. Degradation

| Condition | Behavior |
|-----------|----------|
| No Slack + no Jira | `count=0`, both sources `missing`, metric hidden |
| Slack only | Count repeat Slack incidents; Jira `missing` |
| No Notion | Cannot assess doc update → flag all repeat-incident components as `debt_unknown` or hide metric with warning |

---

## Frontend requirements

### 1. KPI card

```
🔁 Incident knowledge debt    4    → View incidents
```

### 2. Debt list panel

Per row:

- Component name
- `{n} incidents since {date}`
- Last doc edit or "No runbook update"
- Links: Slack thread, Jira ticket (open in new tab)

### 3. Empty state

"No repeat incidents without doc updates" when count=0.

### 4. Integration badge

Show which of Slack / Jira / Notion power this metric (from `data_completeness`).

---

## Tests

`backend/tests/test_kra_incident_knowledge_debt.py`:

- [ ] 2 Slack incidents, no doc update → in debt
- [ ] 2 incidents, doc updated 10d after last → not in debt
- [ ] 1 incident only → not in debt
- [ ] Mixed Slack + Jira on same component → counted together
- [ ] No integrations → metric hidden / zero with flags

---

## Files to touch

| File | Action |
|------|--------|
| `backend/app/services/kra_metrics.py` | Add `compute_incident_knowledge_debt` |
| `backend/app/schemas/kra.py` | Add result models |
| `backend/app/services/integration_telemetry.py` | Helpers to group incidents by component |
| `backend/app/services/cognee_ingest.py` | Optional `GraphSlackIncident` |
| `backend/app/routes/analytics.py` | Extend summary |
| `frontend/src/components/kra/KraDashboard.tsx` | Debt KPI + list |
| `frontend/src/lib/types.ts`, `api.ts` | Types + fetch |

---

## Exit criteria

- [ ] Repeat-incident components without timely doc updates appear in debt list
- [ ] Incident links open correct Slack/Jira URLs
- [ ] Metric uses telemetry cache, not live API calls
- [ ] Partial coverage shown when Notion missing
- [ ] Count is deterministic and test-covered

## Out of scope

- Auto-generating post-incident runbooks
- LLM summarization of Slack threads for scoring
- Incident resolution workflow changes
