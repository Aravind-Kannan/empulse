# KRA Metric 5 — Blast Radius Narrative

> **Prerequisite:** Prompts 1–4 complete.  
> **Sequence:** Prompt 5 of 5 — only metric where Cognee LLM is primary. Adds component detail endpoint.

## Context

KRA Metrics 1–4 are **numbers**. Metric 5 is the **story** that makes leadership care:

> **If this component fails, what else breaks?**

This is the only KRA metric that is **primarily Cognee-powered** — but it produces **qualitative narrative only**, never a numeric score mixed into the org index.

## What exists today

| Area | Location | Notes |
|------|----------|-------|
| Blast radius fetch | `cognee_era_intelligence.fetch_blast_radius_narrative()` | `tenant_graph_search` query |
| ERA detail | `build_employee_detail_intelligence()` | Caches narrative 1h |
| Investigation search | `investigation._search_incident_graph()`, `_fetch_cognee_root_cause_narrative()` | `GRAPH_COMPLETION`, `CHUNKS` patterns |
| Tenant Cognee | `backend/app/services/tenant_cognee.py` | `tenant_graph_search`, `tenant_cognee_context` |
| Component detail API | Not yet standard — create `GET /api/analytics/kra/components/{id}` |

## Task

Implement **Blast Radius Narrative** on per-component KRA drill-down: 2–3 sentence plain-English summary with cited evidence links. Add org-level "top risk narrative" teaser on summary (optional, single component with highest critical SPOF).

---

## Product definition

| Field | Value |
|-------|-------|
| **Display label** | Blast radius |
| **Format** | 2–3 sentences, max 500 chars, no bullet lists in headline card |
| **Example** | "Payments depends on Auth for token validation. Two open P1 Jira tickets block checkout. Last Slack incident was resolved by Alex with no runbook update." |
| **Evidence** | 1–3 source chips below narrative (Jira, Slack, Notion, GitHub PR links) |
| **Refresh** | On-demand + 1h cache per component |

### What narrative must include (when data exists)

1. **Upstream/downstream dependencies** — from Cognee graph (`dependsOn`, `blocksComponent`)
2. **Open operational load** — Jira P1/P2 on component
3. **Recent incident context** — last Slack/Jira incident summary
4. **Doc gap callout** — if Metric 2 flagged this component

Do **not** invent dependencies — if graph is sparse, say "Limited dependency data — connect more integrations."

---

## Backend requirements

### 1. Component detail endpoint

Create:

```
GET /api/analytics/kra/components/{component_id}
```

Response:

```python
class KraComponentDetailResponse(BaseModel):
    component_id: str
    component_name: str
    criticality: str
    is_spof: bool
    bus_factor: int | None
    owners: list[KraOwnerSummary]
    documentation_sources: list[str]
    blast_radius_narrative: str | None
    blast_radius_evidence: list[KraEvidenceSource]
    metrics: KraComponentMetricsSnapshot   # embed flags from metrics 1-4 for this component
    warnings: list[str]                    # e.g. "cognee_degraded"
    generated_at: str
    cache_hit: bool

class KraEvidenceSource(BaseModel):
    provider: Literal["jira", "slack", "notion", "github", "cognee"]
    label: str
    url: str | None

class KraComponentMetricsSnapshot(BaseModel):
    is_critical_spof: bool
    documentation_gap: bool
    incident_debt: bool
    backup_readiness_score: int | None
```

### 2. Narrative builder

Create `backend/app/services/kra_blast_radius.py`:

```python
async def build_blast_radius_narrative(
    db: Session,
    tenant_id: uuid.UUID,
    component_id: str,
    *,
    use_cache: bool = True,
) -> tuple[str | None, list[KraEvidenceSource], list[str]]:
    ...
```

**Pipeline (implement in order):**

#### Step A — Structured context assembly (deterministic)

Gather facts **before** LLM call:

```python
facts = {
    "component_name": ...,
    "owners": [...],
    "open_jira": [...],           # from get_cached_jira_issues, P1/P2 only
    "recent_incidents": [...],     # last 2 Slack threads / Jira bugs, 90d
    "doc_sources": [...],
    "doc_gap": bool,
    "dependent_components": [...], # from DB component relationships if modeled
}
```

#### Step B — Cognee graph completion

```python
query = (
    f"What systems depend on or are blocked by the {component_name} component? "
    f"Owners: {owner_names}. "
    f"Open issues: {jira_keys}. "
    "Use the knowledge graph. Answer in 2-3 sentences for an engineering manager. "
    "Only state facts supported by the graph."
)

async with tenant_cognee_context(tenant_id):
    results = await cognee.search(
        query,
        query_type=SearchType.GRAPH_COMPLETION,
        datasets=[tenant_dataset_name(tenant_id)],
        top_k=5,
    )
```

Reuse patterns from `investigation._fetch_cognee_root_cause_narrative` (timeout 12s, truncate 500 chars).

#### Step C — Evidence chunks (optional enrichment)

```python
chunk_results = await cognee.search(
    f"Dependencies and incidents for {component_name}",
    query_type=SearchType.CHUNKS,
    datasets=[dataset],
    top_k=6,
    include_references=True,
)
```

Parse references into `KraEvidenceSource` — same `_extract_search_text` helpers as investigation.

#### Step D — Merge and guardrails

- If Cognee returns empty → build fallback narrative from Step A facts only (template string, no LLM)
- Strip hallucinated Jira keys not in `facts.open_jira`
- If `CogneeUnavailable` → fallback + `warnings.append("cognee_degraded")`

### 3. Caching

```python
_blast_radius_cache: dict[str, tuple[datetime, str, list[KraEvidenceSource]]] = {}
CACHE_TTL = timedelta(hours=1)
```

Key: `{tenant_id}:{component_id}`.

Invalidate on integration sync for tenant (hook in `integration_sync.py` — optional stub).

### 4. Org-level teaser (summary endpoint)

Extend `GET /api/analytics/kra/summary` with optional field:

```python
class KraSummaryResponse(BaseModel):
    critical_spof: CriticalSpofResult
    documentation_coverage: DocumentationCoverageResult
    incident_knowledge_debt: IncidentKnowledgeDebtResult
    backup_readiness: BackupReadinessResult
    featured_narrative: KraFeaturedNarrative | None  # only if critical SPOF exists

class KraFeaturedNarrative(BaseModel):
    component_id: str
    component_name: str
    narrative: str
```

Pick featured component: first `tier1_revenue` critical SPOF by lowest backup readiness. **Precompute narrative async only if already cached** — do not block summary on Cognee.

### 5. Performance rules

| Endpoint | Cognee |
|----------|--------|
| `GET /kra/summary` | Never blocks on Cognee (cached teaser only) |
| `GET /kra/components/{id}` | Cognee on demand, 12s timeout |
| `GET /kra` (graph) | No Cognee |

---

## Frontend requirements

### 1. Component click → detail panel

When user clicks a component node in KRA graph, fetch `fetchKraComponentDetail(componentId)`:

```
┌─────────────────────────────────────────┐
│ Payments API                    [SPOF]  │
├─────────────────────────────────────────┤
│ Blast radius                            │
│ Payments depends on Auth for token      │
│ validation. Two open P1 tickets...      │
│                                         │
│ [PROJ-101] [Slack #incidents] [Notion]  │
├─────────────────────────────────────────┤
│ Owners · Backups · Docs · Metrics...    │
└─────────────────────────────────────────┘
```

- Loading skeleton while Cognee runs (show "Analyzing dependencies…")
- `cognee_degraded` warning banner with facts-only fallback text
- Evidence chips open URLs in new tab

### 2. Featured narrative on summary (optional)

Below KPI strip, single card:

> **Highest risk: Payments API** — "{narrative teaser…}" [View details]

Only render when `featured_narrative` present.

### 3. Regenerate button

"Refresh analysis" bypasses cache (`?refresh=true` query param).

---

## Tests

`backend/tests/test_kra_blast_radius.py`:

- [ ] Component detail returns 200 with structured fields
- [ ] Cognee timeout → fallback narrative from facts, warning set
- [ ] Cache hit on second request within TTL
- [ ] `refresh=true` bypasses cache
- [ ] Evidence URLs filtered to known Jira/Slack items from telemetry
- [ ] Summary does not block when Cognee slow (featured uses cache only)

Mock Cognee in tests — do not require live Ollama.

---

## Files to touch

| File | Action |
|------|--------|
| `backend/app/services/kra_blast_radius.py` | Create — narrative pipeline |
| `backend/app/services/kra_metrics.py` | `KraComponentMetricsSnapshot` helper |
| `backend/app/schemas/kra.py` | Detail + summary models |
| `backend/app/routes/analytics.py` | `GET /kra/components/{id}`, extend summary |
| `backend/app/services/cognee_era_intelligence.py` | Refactor shared `_result_to_text` if duplicated |
| `frontend/src/components/kra/KraSideDrawer.tsx` | Blast radius section + evidence chips |
| `frontend/src/lib/types.ts`, `api.ts` | `fetchKraComponentDetail` |
| `backend/tests/test_kra_blast_radius.py` | New tests |

---

## Exit criteria

- [ ] Clicking SPOF component shows 2–3 sentence blast radius narrative
- [ ] Evidence chips link to real Jira/Slack/Notion sources
- [ ] Cognee failure degrades gracefully — never 500 on detail
- [ ] Narrative never fabricates ticket keys not in telemetry
- [ ] Summary page load stays fast (&lt;500ms without uncached Cognee)

## Out of scope

- Numeric blast radius score
- Real-time graph traversal UI (keep narrative text)
- Investigation workspace changes (may consume same service later)

---

## Implementation note — tie all 5 metrics together

After completing prompts 01–05, `GET /api/analytics/kra/summary` should return all four numeric metrics plus optional `featured_narrative`. `GET /api/analytics/kra/components/{id}` is the unified drill-down surface combining blast radius + per-component metric snapshot.

Reference orchestrator stub:

```python
def build_kra_summary(db: Session, tenant_id: uuid.UUID) -> KraSummaryResponse:
    return KraSummaryResponse(
        critical_spof=compute_critical_spof_count(db, tenant_id),
        documentation_coverage=compute_documentation_coverage(db, tenant_id),
        incident_knowledge_debt=compute_incident_knowledge_debt(db, tenant_id),
        backup_readiness=compute_backup_readiness(db, tenant_id),
        featured_narrative=_cached_featured_narrative_only(db, tenant_id),
    )
```
