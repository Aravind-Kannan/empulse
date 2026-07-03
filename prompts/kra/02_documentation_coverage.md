# KRA Metric 2 — Documentation Coverage Score

> **Prerequisite:** Prompt 1 complete (`kra_metrics.py`, summary endpoint).  
> **Sequence:** Prompt 2 of 5 — extends summary with doc coverage KPI.

## Context

KRA Metric 2 answers:

> **Is runbook knowledge written down for systems we actually ship code to?**

Undocumented active code = tacit knowledge trap. This is the highest-ROI **preventive** metric — fixable before someone leaves or an incident repeats.

**Scoring rule:** deterministic from graph edges + Notion telemetry. Cognee `GRAPH_COMPLETION` is for drill-down narrative only.

## What exists today

| Area | Location | Notes |
|------|----------|-------|
| Notion doc sources | `kra_analytics._doc_sources_for_component()`, `get_notion_component_sources()` | Per-component doc list |
| Doc gap detection | `cognee_era_intelligence.detect_documentation_gaps()` | Components with code but no Notion |
| Cognee ingest | `backend/app/services/cognee_ingest.py` | `GraphComponent`; `documentedBy` edge planned in Step 10 |
| Notion snapshots | `NotionDocSnapshot` model | `last_edited` timestamps |
| Design reference | `design-docs/era/step-10-cognee-intelligence.md` §10.2 | `Component → documentedBy → NotionPage` |

## Task

Implement **Documentation Coverage Score** (0–100%) as the second KPI in KRA summary. Show org percentage + list of uncovered active components.

---

## Product definition

| Field | Value |
|-------|-------|
| **Display label** | Doc coverage |
| **Headline** | `{pct}% of active systems have current runbooks` |
| **Visual** | Progress ring or bar (green ≥80%, amber 50–79%, red &lt;50%) |
| **Click action** | Side panel listing gap components with "No runbook" / stale doc links |

### Definitions

| Term | Rule |
|------|------|
| **Active component** | Has GitHub ownership data OR ≥1 PR touch in last 90 days (`get_github_activities()`) |
| **Documented** | `get_notion_component_sources(component_id)` returns ≥1 source **OR** Cognee `documentedBy` edge exists |
| **Fresh** | Linked Notion page `last_edited` within 180 days (from `NotionDocSnapshot` or ingest metadata) |
| **Covered** | Documented **and** fresh |

### Formula

```python
active_components = [c for c in components if is_active(c)]
covered = [c for c in active_components if has_fresh_documentation(c)]

coverage_pct = round(100 * len(covered) / len(active_components)) if active_components else None
gap_components = [c for c in active_components if c not in covered]
```

Return `coverage_pct: int | None` — `None` when no active components (show "—" in UI, not 0%).

---

## Backend requirements

### 1. Service function

In `backend/app/services/kra_metrics.py`:

```python
def compute_documentation_coverage(
    db: Session,
    tenant_id: uuid.UUID,
) -> DocumentationCoverageResult:
    ...
```

```python
class DocumentationGapComponent(BaseModel):
    component_id: str
    component_name: str
    gap_reason: Literal["missing", "stale"]
    last_doc_edit: str | None          # ISO date or None
    notion_sources: list[str]            # empty if missing
    days_since_activity: int | None

class DocumentationCoverageResult(BaseModel):
    coverage_pct: int | None
    active_component_count: int
    covered_count: int
    gap_components: list[DocumentationGapComponent]
    data_completeness: KraMetricCoverage
```

### 2. Cognee integration

**Ingest (if `documentedBy` not wired):**

In `cognee_ingest.py` or Notion sync path, add edge:

```python
Edge(
    source=component_node,
    target=notion_page_node,
    relationship="documentedBy",
)
```

Persist on each Notion sync when page maps to component.

**Query (summary):** Prefer SQL/telemetry (`get_notion_component_sources`, `NotionDocSnapshot`) — faster than Cognee.

**Query (drill-down narrative):** On `GET /api/analytics/kra/components/{id}`:

```python
query = f"What documentation exists for the {component_name} system? Include runbooks and architecture pages."
# tenant_graph_search or GRAPH_COMPLETION, top_k=5, cache 1h
```

### 3. API

Extend `GET /api/analytics/kra/summary`:

```json
{
  "documentation_coverage": {
    "coverage_pct": 62,
    "active_component_count": 8,
    "covered_count": 5,
    "gap_components": [...],
    "data_completeness": { "notion": "confirmed", "github": "confirmed" }
  }
}
```

### 4. Coverage / degradation

| Missing integration | Behavior |
|---------------------|----------|
| Notion not connected | `coverage_pct=None`, `notion: "missing"`, hide score — show "Connect Notion" CTA |
| GitHub not connected | Treat all assigned components as active (assignment-based); flag `partial` |
| Both missing | Metric hidden with explanation |

---

## Frontend requirements

### 1. KPI card on `/kra`

```
📄 Doc coverage    62%    → View gaps
```

- Ring/bar visualization
- Partial badge when Notion or GitHub incomplete
- Notion missing → card shows setup link from `integrations.ts` requirements

### 2. Gap list panel

Slide-over or expandable section:

| Component | Status | Action |
|-----------|--------|--------|
| Payments API | Missing runbook | — |
| Auth Service | Stale (240d) | Open Notion link |

### 3. Component detail

When clicking a gap row, open existing KRA side drawer with `documentation_sources` + Cognee narrative (if loaded).

---

## Tests

`backend/tests/test_kra_documentation_coverage.py`:

- [ ] 3 active, 2 covered → 67%
- [ ] Stale doc (&gt;180d) → gap_reason=`stale`
- [ ] No Notion → `coverage_pct=None`, notion missing flag
- [ ] No active components → `coverage_pct=None`
- [ ] Fresh Notion source → component counted as covered

---

## Files to touch

| File | Action |
|------|--------|
| `backend/app/services/kra_metrics.py` | Add `compute_documentation_coverage` |
| `backend/app/schemas/kra.py` | Add result models |
| `backend/app/services/cognee_ingest.py` | Wire `documentedBy` if missing |
| `backend/app/services/integration_sync.py` | Notion sync → documentedBy edges |
| `backend/app/routes/analytics.py` | Extend summary |
| `frontend/src/components/kra/KraDashboard.tsx` | Coverage KPI + gap panel |
| `frontend/src/lib/types.ts`, `api.ts` | Types + fetch |

---

## Exit criteria

- [ ] Coverage % visible on `/kra` when Notion + GitHub connected
- [ ] Gap list shows missing vs stale with correct reasons
- [ ] Score is reproducible without Cognee LLM
- [ ] Component drill-down can show Cognee doc narrative (cached)
- [ ] Honest empty state when Notion not connected

## Out of scope

- Auto-creating Notion pages
- Full-text doc quality scoring
- ERA D-dimension duplication (KRA owns org-level doc coverage; ERA references it per employee)
