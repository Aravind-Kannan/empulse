# Step 12 — Mitigations and Actions

**Depends on:** 09  
**Blocks:** **16** (Exit bridge consumes mitigations)  
**Estimate:** 3–4 days

## Exit module integration (Step 16)

Open mitigations with `status=open` are included in ERA-prefilled handover markdown when user clicks “Start exit handover” from ERA detail.

## Goal

Turn evidence into trackable actions — recommendations with owners, due dates, and status — so ERA drives remediation, not just anxiety.

## Mitigation rule engine

```python
MITIGATION_RULES: list[MitigationRule] = [
    MitigationRule(
        condition=lambda e: e.dimensions.knowledge > 70 and has_backup(e),
        action="Pair on next 2 PRs with backup engineer",
        priority="high",
        link_template="/settings/org-chart",
    ),
    MitigationRule(
        condition=lambda e: e.dimensions.knowledge > 70 and not has_backup(e),
        action="Add backup owner in CODEOWNERS",
        priority="critical",
        link_template="{github_repo}/settings/codeowners",
    ),
    MitigationRule(
        condition=lambda e: e.dimensions.documentation > 50,
        action="Schedule runbook update sprint",
        priority="medium",
        link_template="{notion_runbook_url}",
    ),
    MitigationRule(
        condition=lambda e: e.dimensions.operational > 60,
        action="Redistribute Jira epics across team",
        priority="high",
        link_template="{jira_filter_url}",
    ),
    MitigationRule(
        condition=lambda e: e.departure_watchlist,
        action="Manager workload review — burnout signals detected",
        priority="medium",
        link_template=None,
    ),
]
```

## Evidence mitigation status

Extend `EraEvidenceItem`:

```python
mitigation_status: open | in_progress | done | dismissed
mitigation_assignee_id: str | None
mitigation_due_date: date | None
mitigation_notes: str | None
```

## API

```
PATCH /api/analytics/era/evidence/{evidence_id}
Body: { mitigation_status, assignee_id?, due_date?, notes? }
```

Persist in `EraEvidenceMitigation` table keyed by `(tenant, employee_id, evidence_id)`.

## UI (`EraMitigationChecklist`)

In employee detail drawer:

```
Recommended actions
☐ Add backup owner in CODEOWNERS          [Assign] [Done]
☐ Schedule runbook update for Auth        [Assign] [Done]
☑ Pair on next 2 PRs (marked done Jan 12)
```

Team-level view on command center (optional v2):

```
Open mitigations: 12 across team · 3 overdue
```

## Auto-suggestions from evidence

When evidence item created, attach `suggested_mitigation` string from rule engine.

## Edge cases

| Case | Handling |
|------|----------|
| Evidence id changes on recompute | Stable hash id: `hash(dimension + title + component_id)` |
| Dismissed false positive | Status `dismissed`; don't re-open unless signal worsens 2x |
| Done but signal persists | Re-open with note "recurring" |
| No assignee in system | Assign to manager from org chart |
| Contractor evidence | Mitigation assigned to EM not contractor |

## Metrics (team health)

Track over time:

- `open_mitigations_count`
- `mean_time_to_mitigate_days`
- `dismissed_rate` (watch for abuse)

## Integration with Exit module

High-risk employee + open mitigations → pre-populate Employee Exit handover checklist.

## Testing

- [ ] Rule triggers for Frank high-K fixture
- [ ] PATCH updates status
- [ ] Dismissed evidence hidden from open count

## Exit criteria

- [ ] Each high-severity evidence has suggested action
- [ ] Managers can mark mitigations done
- [ ] Stable evidence ids across recomputes

## Files to touch

- `backend/app/models/operational.py` — `EraEvidenceMitigation`
- `backend/app/services/era_mitigations.py` — new
- `backend/app/routes/analytics.py`
- `frontend/src/components/era/EraMitigationChecklist.tsx`

## References

- [WorkFera capture plans](https://www.workfera.com/solutions/knowledge-risk-review) — ranked remediation cadence
- [ContributorIQ knowledge transfer lists](https://contributoriq.com/use-cases/departure-risk) — prioritized handover workflows
