# Step 11 — Trends and Rollups

**Depends on:** 03, **18** (org health trends)  
**Estimate:** 4–5 days

## Org health & orphan trends (Step 18)

Extend snapshots to include:

```python
class EraTeamSnapshot(Base):
    snapshot_date, tenant_id
    avg_risk_score, org_health_score
    orphan_file_count, orphan_delta_90d
```

## Goal

Persist daily risk snapshots, show 7d/30d trends, and provide manager team roll-up views.

## Data model

```python
class EraRiskSnapshot(Base):
    __tablename__ = "era_risk_snapshots"
    id: UUID
    tenant_id: UUID
    employee_id: str
    snapshot_date: date          # UTC date
    risk_factor_score: float
    risk_level: str
    dimensions_json: dict        # {K,O,D,S,B}
    computed_at: datetime

    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "snapshot_date"),
    )
```

## Snapshot job

Trigger after successful global sync or nightly cron:

```python
def snapshot_era_metrics(db, tenant) -> int:
    metrics = compute_era_metrics(db, tenant)
    for emp in metrics.employees:
        upsert EraRiskSnapshot for today
```

## Trend calculation

```python
def trend_7d(current: float, snapshots: list[float]) -> float | None:
    if len(snapshots) < 2:
        return None
    week_ago = snapshots[-7] if len(snapshots) >= 7 else snapshots[0]
    return round(current - week_ago, 1)
```

Expose `trend_7d` on `EraEmployeeMetrics` and `team_summary.avg_risk_trend_7d`.

## UI integration

| Surface | Element |
|---------|---------|
| KPI strip Team Risk | `▲ +4` or `▼ -2` chip |
| Heatmap row | Small sparkline (optional v2) |
| Team composition | 30d team avg sparkline |
| Detail drawer | Risk history line chart |

## Manager roll-up

For employees with `direct_reports > 0`:

```python
def manager_team_risk(manager_id: str) -> ManagerRollup:
    reports = get_direct_reports(manager_id)
    return ManagerRollup(
        team_avg_risk=mean(r.risk_factor_score for r in reports),
        high_risk_report_count=sum(1 for r in reports if r.risk_level == "high"),
        manager_exposure_bonus=min(15, high_risk_report_count * 5),  # feeds S dimension
    )
```

Optional endpoint:

```
GET /api/analytics/era/rollup?manager_id={id}
```

## Manager view (future tab on `/era`)

Filter heatmap to `manager_id` subtree (1 level or recursive config).

## Edge cases

| Case | Handling |
|------|----------|
| First week, no history | Hide trend chips (`null`) |
| Employee joined mid-week | Snapshot from join date only |
| Score algorithm change | Bump `snapshot_version`; optional reset |
| Deleted employee | Keep snapshots; mark inactive |
| Timezone | Store UTC dates consistently |
| Duplicate snapshot same day | Upsert idempotent |

## Retention

- Keep 365 days per tenant
- Archive older to cold storage (optional)

## Testing

- [ ] Snapshot idempotent on re-run same day
- [ ] trend_7d correct with fixture snapshots
- [ ] Manager roll-up excludes leadership

## Exit criteria

- [ ] Nightly snapshots running
- [ ] `trend_7d` on API and KPI strip
- [ ] Detail drawer shows 30d line chart

## Files to touch

- `backend/app/models/operational.py` — `EraRiskSnapshot`
- `backend/app/services/era_snapshots.py` — new
- `backend/app/jobs/` or sync hook — snapshot trigger
- `frontend/src/components/era/EraRiskSparkline.tsx`
- `frontend/src/components/era/EraDetailHistoryChart.tsx` — new
