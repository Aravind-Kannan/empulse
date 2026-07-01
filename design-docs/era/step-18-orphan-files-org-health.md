# Step 18 — Orphan Files & Organization Health Score

**Depends on:** 11, 14  
**Estimate:** 3–4 days  
**Reference:** [ContributorIQ — orphan risk & org health](https://contributoriq.com/)

## Goal

Track **orphan files** (no active author) and expose a **team resilience score** complementary to avg ERA risk %.

## Orphan file detection

File is **orphan** when:

- No contributor with DOA > 0.75 in last 90d, AND
- File had activity in prior 12 months (not dead code)

### Post-departure tracking

When `Employee.active` set to `false`:

1. Snapshot files where employee was sole author (DOA > 0.75)
2. On subsequent syncs, count files that became orphan → `orphan_delta_after_departure`

## Organization Health Score (0–100)

Composite **team resilience** (not individual ERA):

| Factor | Weight | Source |
|--------|--------|--------|
| Bus factor score | 25% | Avg component bus factor (Step 14) |
| Single-author file rate | 25% | % files with bus factor 1 |
| Knowledge spread (Gini) | 25% | Commit/DOA distribution across team |
| Activity diversity | 25% | # contributors active in 90d / team size |

```
org_health = weighted sum, higher = healthier
```

Display on KPI strip **alongside** avg ERA risk (inverse framing: low ERA + high org health = good).

## API

```typescript
team_summary: {
  // existing fields...
  org_health_score: number;      // 0-100
  orphan_file_count: number;
  orphan_delta_90d: number;
}
```

## Evidence

```
🟠 14 files became orphaned after {former employee} departure
Affected: payments/handler.ts, ...
```

## Edge cases

| Case | Handling |
|------|----------|
| Small team (n<3) | Gini unreliable — show with caution flag |
| Legacy archive repos | Exclude via repo allowlist |
| Re-hire | Orphan may resolve — update on sync |

## Exit criteria

- [ ] `org_health_score` on team_summary
- [ ] Orphan count trends in Step 11 snapshots
- [ ] Departure triggers orphan baseline snapshot

## Files to touch

- `backend/app/services/github_orphans.py` — new
- `backend/app/services/era/org_health.py` — new
- `backend/app/schemas/era.py`
- `frontend/src/components/era/EraKpiStrip.tsx` — org health card
