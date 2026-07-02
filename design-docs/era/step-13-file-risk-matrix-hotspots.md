# Step 13 — File Risk Matrix & Hotspots

**Depends on:** 04 (live GitHub), 14 (DOA recommended)  
**Blocks:** 08 (matrix widget), KRA enhancements  
**Estimate:** 4–5 days  
**Reference:** [CodePulse — Knowledge silos & hotspots](https://codepulsehq.com/features/knowledge-silos)

## Goal

Surface **file-level** risk via a churn × ownership matrix (hotspot × bus-factor), complementing the people-level ERA heatmap (Step 08).

## Risk matrix quadrants

| | Low churn | High churn |
|---|-----------|------------|
| **Few contributors (≤2)** | Stable niche | **Critical** — high-churn silo |
| **Many contributors (≥3)** | Healthy | Active shared code |

**Thresholds (configurable per tenant):**

- High churn: ≥11 commits/quarter on file (or ≥3 distinct PRs in 90d)
- Few contributors: ≤2 unique authors in analysis window
- `min_touches`: 3 PRs before flagging silo (ignore one-off edits)

## Data model

```python
class FileRiskSnapshot(Base):
    tenant_id, component_id, repo_path, file_path
    churn_score: int           # PR touches in window
    contributor_count: int
    bus_factor: int            # distinct authors with DOA > 0.75
    quadrant: str              # critical | stable_niche | active_shared | healthy
    primary_owner_employee_id: str | None
    computed_at: datetime
```

## API

```
GET /api/analytics/kra/file-risk?component_id=
GET /api/analytics/era/{employee_id}/hotspots  # files where employee is primary owner in critical quadrant
```

## UI

- **KRA:** full 2×2 matrix per component; dots = files sized by churn
- **ERA detail (Step 09):** mini-matrix for `affected_components`
- **Command center (Step 08):** optional “Critical files” KPI count

## Evidence

```
🔴 Critical file — payments/handler.ts
High churn (14 PRs/90d), bus factor 1, you are primary owner (DOA 0.88)
[View on GitHub]
```

## Edge cases

| Case | Handling |
|------|----------|
| Test/vendor paths | Exclude via glob (`**/test/**`, `package-lock.json`) |
| Monorepo unmapped paths | Bucket under component or `unmapped` |
| Generated code | Exclude via `.gitattributes` or config |
| Renamed files | Follow git rename detection |

## Exit criteria

- [ ] Critical quadrant files feed K dimension evidence
- [ ] KRA page shows matrix for at least one component
- [ ] Cross-training priority list = sorted critical files

## Files to touch

- `backend/app/services/github_file_risk.py` — new
- `backend/app/routes/analytics.py`, `kra` routes
- `frontend/src/components/kra/FileRiskMatrix.tsx` — new
- `frontend/src/components/era/EraHotspotSummary.tsx` — new
