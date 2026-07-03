# KRA Metric 1 — Critical SPOF Count

> **Prerequisite:** Read `prompts/kra/00_product_design.md` first.  
> **Sequence:** Prompt 1 of 5 — scaffolds `GET /api/analytics/kra/summary`.

## Context

Empulse **Knowledge Risk Assessment (KRA)** is component-centric: it shows where critical knowledge is trapped in systems, not people. Metric 1 answers the highest-leverage leadership question:

> **How many revenue-critical systems have only one real owner?**

This metric must be **deterministic** (SQL + telemetry + graph edge counts). Do **not** derive the number from Cognee LLM search — Cognee is used only for evidence enrichment on drill-down, not for scoring.

## What exists today

| Area | Location | Notes |
|------|----------|-------|
| KRA graph API | `GET /api/analytics/kra` → `backend/app/services/kra_analytics.py` | Sets `is_spof`, `github_verified_spof`, `bus_factor` per component node |
| Bus factor | `integration_telemetry.get_all_bus_factors()`, `is_github_spof()` | GitHub DOA-derived |
| Component criticality | `Component` model — check for `criticality` or tier field; if missing, default `tier2_core` |
| ERA cross-link | `frontend/src/components/era/EraKpiStrip.tsx` links to `/kra?filter=spof` |
| Design reference | `design-docs/era/step-10-cognee-intelligence.md` | Rule: never use free-text search for scores |

## Task

Implement **Critical SPOF Count** as the first KPI in a new KRA summary layer. Expose org-level count + per-component list for drill-down. Integrate into `/kra` dashboard header.

---

## Product definition

| Field | Value |
|-------|-------|
| **Display label** | Critical SPOFs |
| **Headline** | `{n} revenue-critical systems have no backup` (n = count) |
| **Severity** | Red if n > 0, green if n = 0 |
| **Click action** | Filter graph to SPOF components where `criticality = tier1_revenue` (or equivalent) |

### Formula (implement exactly)

A component is a **critical SPOF** when **all** of:

1. `criticality` is `tier1_revenue` (or highest tier in your schema)
2. **Either** `bus_factor <= 1` (GitHub-verified when `has_github_sync()`)
   **Or** `distinct owner count <= 1` from assignment/GitHub ownership links

```python
is_critical_spof = (
    component.criticality == "tier1_revenue"
    and (
        (has_github_sync() and bus_factor.get(component_id, 99) <= 1)
        or len(owners_for_component) <= 1
    )
)
```

Org metric = `count(is_critical_spof)` across tenant components.

---

## Backend requirements

### 1. Service module

Create `backend/app/services/kra_metrics.py` (or extend `kra_analytics.py` if already small) with:

```python
def compute_critical_spof_count(
    db: Session,
    tenant_id: uuid.UUID,
) -> CriticalSpofResult:
    ...
```

Return:

```python
class CriticalSpofComponent(BaseModel):
    component_id: str
    component_name: str
    bus_factor: int | None
    owner_count: int
    owner_names: list[str]          # max 3 for UI
    github_verified: bool
    criticality: str

class CriticalSpofResult(BaseModel):
    count: int
    components: list[CriticalSpofComponent]
    data_completeness: KraMetricCoverage  # shared partial-coverage model
```

### 2. API endpoint

Add to `backend/app/routes/analytics.py`:

```
GET /api/analytics/kra/summary
```

Response includes `critical_spof: CriticalSpofResult` plus placeholders for other metrics (can be stubbed empty until later prompts).

Alternatively, if summary endpoint not ready, add:

```
GET /api/analytics/kra/metrics/critical-spof
```

Prefer **one summary endpoint** that grows with prompts 02–05.

### 3. Cognee usage (evidence only)

On component drill-down (`GET /api/analytics/kra/components/{id}` — create stub if missing):

- Use structured graph: `Employee → ownsComponent → Component` to list owners
- Optional: `tenant_graph_search` with `top_k=3` for narrative evidence — **never** for count

### 4. Performance

- **No live Cognee** on list/summary — SQL + `integration_telemetry` only
- Cache summary 5 min per tenant (in-memory dict, same pattern as `incident_feed` cache)

### 5. Degradation

| Condition | Behavior |
|-----------|----------|
| No GitHub sync | Use assignment-only owner count; set `github_verified=False`; flag `partial` on coverage |
| No components | `count=0`, empty list |
| Demo / Acme fallback | Use `ACME_ORG_CHART` when tenant has zero employees |

---

## Frontend requirements

### 1. Types

Add to `frontend/src/lib/types.ts` mirroring backend schemas.

### 2. API client

Add `fetchKraSummary()` in `frontend/src/lib/api.ts`.

### 3. UI — `frontend/src/components/kra/KraDashboard.tsx`

Add KPI strip above graph (match `EraKpiStrip` visual language):

```
🔴 Critical SPOFs    3    → View components
```

- Click → apply `?filter=spof` or internal filter state highlighting tier-1 SPOF nodes
- Tooltip: one-line formula explanation
- Show `partial` badge when GitHub not connected

### 4. Graph integration

When filter active, pulse red only nodes matching critical SPOF definition (not all structural SPOFs).

---

## Tests

Add `backend/tests/test_kra_critical_spof.py`:

- [ ] Tier-1 component, bus_factor=1 → counted
- [ ] Tier-1 component, bus_factor=3, 2 owners → not counted
- [ ] Tier-3 component, bus_factor=1 → not counted
- [ ] No GitHub → assignment-only path works
- [ ] Summary endpoint returns 200 with coverage flags

---

## Files to touch

| File | Action |
|------|--------|
| `backend/app/services/kra_metrics.py` | Create — metric computation |
| `backend/app/schemas/kra.py` | Add `CriticalSpofResult`, `KraSummaryResponse` |
| `backend/app/routes/analytics.py` | Add summary route |
| `frontend/src/lib/types.ts` | Mirror schemas |
| `frontend/src/lib/api.ts` | `fetchKraSummary` |
| `frontend/src/components/kra/KraDashboard.tsx` | KPI strip + filter |
| `backend/tests/test_kra_critical_spof.py` | New tests |

---

## Exit criteria

- [ ] Manager sees critical SPOF count in &lt;30s on `/kra`
- [ ] Count matches manual inspection of tier-1 + bus_factor≤1 components
- [ ] Click drills to filtered graph view
- [ ] No Cognee LLM call on summary load
- [ ] Partial data state visible when GitHub missing

## Out of scope

- Assigning backups (existing `POST /api/analytics/kra/assign-backup`)
- File-level hotspot matrix (`GET /api/analytics/kra/file-risk`)
- ERA person-level risk scoring
