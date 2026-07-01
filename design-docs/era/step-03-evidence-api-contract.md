# Step 03 — Evidence API Contract

**Depends on:** 02 (+ connector steps for live data)  
**Blocks:** 08, 09, 10, 11  
**Estimate:** 2–3 days

## Goal

Define and implement API v2 so the Command Center UI loads **all team insights in one request**.

## Endpoints

```
GET  /api/analytics/era
GET  /api/analytics/era/{employee_id}   # full evidence list
POST /api/analytics/era/recompute      # admin: force refresh (optional)
```

## Response: `GET /api/analytics/era`

```typescript
interface EraAnalyticsResponse {
  computed_at: string;              // ISO-8601
  demo_mode: boolean;
  warnings: string[];               // e.g. "github_stale", "partial_identity"

  team_summary: EraTeamSummary;
  employees: EraEmployeeMetrics[];

  unmapped_activity: {
    provider: IntegrationId;
    count: number;
  }[];

  sync_freshness: Partial<Record<
    IntegrationId,
    string | null   // ISO timestamp of last successful sync
  >>;
}
```

### `EraTeamSummary`

```typescript
interface EraTeamSummary {
  avg_risk_score: number;
  high_risk_count: number;          // risk_level === "high"
  medium_risk_count: number;
  low_risk_count: number;
  spof_component_count: number;
  open_p1_count: number;
  undocumented_incident_count: number;
  top_risk_driver: EraDimensionKey; // highest avg dimension across team
  estimated_recovery_weeks: { min: number; max: number };
  data_health_pct: number;            // avg data_completeness_pct
  org_health_score?: number;          // Step 18 — team resilience 0-100
  critical_hotspot_count?: number;    // Step 13
  last_risk_review_at?: string | null; // Step 17
  unacknowledged_alert_count?: number; // Step 17
}
```

### `EraEmployeeMetrics` (extended)

```typescript
type EraDimensionKey =
  | "knowledge"
  | "operational"
  | "documentation"
  | "structural"
  | "burnout";

type IdentityCoverageLevel = "confirmed" | "high" | "missing";

interface EraDimensions {
  knowledge: number;
  operational: number;
  documentation: number;
  structural: number;
  burnout: number;
  partial?: Partial<Record<EraDimensionKey, boolean>>;
}

interface EraEmployeeMetrics {
  // Legacy (backward compatible)
  employee_id: string;
  name: string;
  role: string;
  email: string;
  unresolved_issues: number;
  open_tasks: number;
  undocumented_solved_incidents: number;
  codebase_share_pct: number;
  risk_factor_score: number;
  risk_level: "low" | "medium" | "high";
  jira_backlog_boost: number;

  // v2
  dimensions: EraDimensions;
  evidence: EraEvidenceItem[];       // top 5 by impact_points
  evidence_total_count: number;
  affected_components: EraAffectedComponent[];
  identity_coverage: Record<IntegrationId, IdentityCoverageLevel>;
  data_completeness_pct: number;     // 0-100
  recovery_estimate_weeks?: { min: number; max: number };
  departure_watchlist?: boolean;     // B > 60
  trend_7d?: number | null;          // Step 11; null until snapshots exist
  org_health_context?: string;       // Step 18 — team resilience note
  critical_hotspot_count?: number;   // Step 13
  excluded?: boolean;                // leadership
  exclusion_reason?: string;
}

interface EraAffectedComponent {
  id: string;
  name: string;
  spof: boolean;
  criticality: "tier1_revenue" | "tier2_core" | "tier3_support";
  ownership_pct?: number;
}

interface EraEvidenceItem {
  id: string;
  dimension: EraDimensionKey;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  impact_points: number;
  sources: {
    provider: IntegrationId;
    label: string;
    url: string | null;
  }[];
  synthetic?: boolean;              // true if placeholder data
  mitigation_status?: "open" | "in_progress" | "done" | "dismissed";
}
```

## Evidence rules

1. Sort by `impact_points` descending
2. List endpoint: max **5** items per employee
3. Detail endpoint: all items, paginated `?limit=20&offset=0`
4. Severity mapping:
   - `impact_points >= 15` → high
   - `impact_points >= 8` → medium
   - else → low
5. Every item must have `title` + `description` suitable for UI cards
6. `sources[].url` required when URL is known; `null` allowed with label only

## Team-wide evidence feed (for Step 08)

Derive from all employees' evidence:

```python
def team_evidence_feed(employees, limit=10) -> list[EraEvidenceItem]:
    flat = [e for emp in employees for e in emp.evidence]
    return sorted(flat, key=lambda x: x.impact_points, reverse=True)[:limit]
```

Expose as `team_evidence_feed` on list response (optional field).

## Pydantic schemas

- `backend/app/schemas/era.py` — extend models
- `frontend/src/lib/types.ts` — mirror types

## Caching

| Strategy | Detail |
|----------|--------|
| Compute on sync complete | Primary path |
| On-demand | `GET /era` if `computed_at` older than sync |
| ETag | Hash of `(tenant_id, employee_ids, computed_at)` |

## Edge cases

| Case | Response |
|------|----------|
| Empty tenant, no employees | `employees: []`, zeros in summary, `demo_mode: true` if Acme fallback used |
| Stale sync (>24h) | `warnings: ["github_stale"]`, amber in UI |
| Leadership employees | `excluded: true`, omitted from `employees` or in separate `excluded_employees` |
| Partial identity | `data_completeness_pct < 100`, per-dimension `partial` |
| Synthetic undocumented count | `evidence[].synthetic: true` |
| 200+ employees | Defer pagination; document max 500 per tenant for v1 |

## Migration

1. Ship v2 fields alongside legacy fields
2. Frontend reads v2 when `dimensions` present
3. Remove feature flag after Step 08 ships

## Testing

- [ ] OpenAPI schema validates
- [ ] Frontend `fetchEraMetrics` parses v2
- [ ] Legacy clients still work with old fields only
- [ ] `demo_mode: true` when `_fallback_acme_metrics()` used

## Exit criteria

- [ ] `GET /api/analytics/era` returns full `team_summary` + extended employees
- [ ] `GET /api/analytics/era/{id}` returns full evidence
- [ ] Types synced in `frontend/src/lib/types.ts`

## Files to touch

- `backend/app/schemas/era.py`
- `backend/app/routes/analytics.py`
- `backend/app/services/era_analytics.py`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
