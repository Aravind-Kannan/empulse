# Step 17 — Proactive Alerts & Knowledge Risk Review Cadence

**Depends on:** 03, 08, 11  
**Estimate:** 3–5 days  
**Reference:** [CodePulse alerts](https://codepulsehq.com/guides/code-hotspots-knowledge-silos), [WorkFera knowledge risk review](https://www.workfera.com/solutions/knowledge-risk-review)

## Goal

Push critical ERA signals to managers (not only pull via dashboard) and institutionalize **periodic knowledge risk reviews**.

## Alert rules (configurable per tenant)

| Rule ID | Condition | Channel |
|---------|-----------|---------|
| `spof_tier1` | New SPOF on `tier1_revenue` component | In-app + Slack webhook |
| `critical_file` | File enters critical quadrant (Step 13) | In-app |
| `unassigned_p1` | Unassigned P1 on owned component | In-app + evidence feed |
| `identity_gap` | `unmapped_count` > threshold | In-app → identity settings |
| `stale_sync` | Integration stale > 24h | In-app banner |
| `risk_review_due` | No team review in > 30 days | In-app banner |

**Ethics:** alerts go to **team channels** (`#eng-leadership`), not DMs naming individuals unless manager subscribes to direct reports only.

## Data model

```python
class EraAlert(Base):
    id, tenant_id, rule_id, severity, title, description
    employee_id: str | None      # optional — component-level alerts may omit
    component_id: str | None
    evidence_id: str | None
    created_at, acknowledged_at, acknowledged_by

class EraTeamReview(Base):
    tenant_id, reviewed_at, reviewer_user_id
    notes: str | None
    snapshot_avg_risk: float
    delta_since_last: float | None
```

## Knowledge risk review cadence

- EM completes “ERA review” monthly (configurable)
- Command center banner: “Last team risk review: 47 days ago [Mark reviewed]”
- `POST /api/analytics/era/reviews` — records review + optional notes

## API

```
GET  /api/analytics/era/alerts?unacknowledged=true
POST /api/analytics/era/alerts/{id}/acknowledge
GET  /api/analytics/era/reviews
POST /api/analytics/era/reviews
```

## Slack webhook payload (optional)

```json
{
  "text": "ERA: New SPOF on Payments (tier1). 1 critical file. View: https://app/era"
}
```

## Edge cases

| Case | Handling |
|------|----------|
| Alert storm on first sync | Suppress duplicates 24h; batch summary |
| Demo mode | No external webhooks |
| Acknowledged but condition persists | Re-alert after 7d if worsened |

## Exit criteria

- [ ] At least 3 alert rules firing on test fixtures
- [ ] Review cadence banner on command center
- [ ] Slack webhook integration optional in settings

## Files to touch

- `backend/app/services/era_alerts.py` — new
- `backend/app/routes/analytics.py`
- `frontend/src/components/era/EraAlertsBanner.tsx`
- `frontend/src/app/settings/` — webhook config
