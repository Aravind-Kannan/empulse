# Step 15 — Review Network & Risky Changes

**Depends on:** 04, 14  
**Blocks:** 10 (backup candidates), 02 (K backup score)  
**Estimate:** 4–6 days  
**Reference:** [CodePulse — Review network](https://codepulsehq.com/features)

## Goal

Map **who reviews whom**, detect review bottlenecks, and flag **risky changes** — improving backup-candidate detection beyond LOC/DOA.

## Review network

Build directed graph from GitHub PR reviews:

```
Reviewer → Author (edge weight = review count in 90d)
```

### Metrics per employee

| Metric | Use |
|--------|-----|
| `review_concentration_pct` | % of their PRs reviewed by top 1 reviewer |
| `reviews_given_count` | Backup signal for others |
| `sole_reviewer_count` | PRs with only one reviewer (risk) |
| `isolation_score` | Few reviews given/received |

### Backup candidate boost (Step 10)

```python
backup_score = doa_secondary * 0.6 + review_count_on_their_prs * 0.4
label = "ramping" if recent_reviews >= 3 else "secondary"
```

## Risky change detection

Flag PRs merged in analysis window:

| Rule | Severity |
|------|----------|
| Merged without approval | high |
| Single author + touches SPOF/bus-factor-1 files | high |
| LOC > p95 for team | medium |
| Touches `tier1_revenue` + sole reviewer | high |

Link to Investigation module where relevant.

## API

```
GET /api/analytics/era/{employee_id}/review-network
GET /api/analytics/team/risky-changes?since=90d
```

## UI

- **ERA detail:** small review network subgraph (who reviews this person’s PRs)
- **Evidence feed:** risky change events team-wide
- Frame as **system health**, not individual performance

## Edge cases

| Case | Handling |
|------|----------|
| Bot approvals | Exclude |
| Self-merge admin | Flag if bypasses branch protection |
| External reviewers | Map via identity or skip |
| Stale open PRs | Don’t count as merged risky |

## Exit criteria

- [ ] `backup_review_score` in K dimension uses real review data
- [ ] Evidence: “No backup reviewer on last N PRs” with PR links
- [ ] Risky changes appear in team evidence feed

## Files to touch

- `backend/app/services/github_reviews.py` — new
- `backend/app/services/era/dimensions.py`
- `backend/app/services/cognee_era_intelligence.py`
- `frontend/src/components/era/EraReviewNetwork.tsx` — new
