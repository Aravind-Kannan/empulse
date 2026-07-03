# KRA Metric 4 — Backup Readiness Index

> **Prerequisite:** Prompts 1–3 complete. Reuses `find_backup_candidates()`.  
> **Sequence:** Prompt 4 of 5 — SPOF mitigation quality index.

## Context

KRA Metric 4 answers the operational question SPOF count alone cannot:

> **For single-owner systems, is there someone who could take over in days — not months?**

A SPOF with a **ramping** secondary engineer (recent reviews + commits) is materially less risky than a SPOF with zero backup.

**Scoring:** deterministic from existing backup candidate ranking. Cognee graph traversal validates `Employee O → contributedTo → Component C` relationships for evidence links.

## What exists today

| Area | Location | Notes |
|------|----------|-------|
| Backup ranking | `cognee_era_intelligence.find_backup_candidates()` | DOA 40% + reviews 35% + commits 25% |
| Backup labels | `_backup_label()` — `ramping` if reviews ≥ 3 | |
| SPOF detection | `kra_analytics`, `is_github_spof()` | |
| Assign backup API | `POST /api/analytics/kra/assign-backup` | Creates assignment, checks `is_spof_resolved` |
| Review network | `get_review_network()` | Step 15 edges |
| Design reference | `design-docs/era/step-10-cognee-intelligence.md` §10.1 | Top 3 backups per SPOF component |

## Task

Implement **Backup Readiness Index** (0–100%) at org level: average backup quality across all SPOF components (structural or GitHub-verified).

---

## Product definition

| Field | Value |
|-------|-------|
| **Display label** | Backup readiness |
| **Headline** | `Backup readiness: {pct}%` |
| **Interpretation** | Low (&lt;40%) = most SPOFs lack a ramping secondary |
| **Click action** | Table of SPOF components → top backup candidate or "None identified" → link to assign flow |

### Definitions

| Term | Rule |
|------|------|
| **SPOF component** | Same as existing KRA graph: `is_spof=True` on component node (structural ≤1 owner OR `github_verified_spof`) |
| **Backup candidate** | From `find_backup_candidates(db, tenant_id, primary_owner_id, component_id, limit=1)` — highest score |
| **Component readiness** | `0` if no candidate; else `min(100, candidate.score * 20)` — scale 0–5 score → 0–100 |
| **Ramping bonus** | If top candidate `label == "ramping"`, add +10 (cap 100) |

### Formula

```python
spof_components = [c for c in components if is_spof(c)]

readiness_scores: list[float] = []
for spof in spof_components:
    primary_owner = dominant_owner(spof)  # highest codebase_share_pct
    if not primary_owner:
        readiness_scores.append(0.0)
        continue
    candidates = find_backup_candidates(..., employee_id=primary_owner, limit=1)
    if not candidates:
        readiness_scores.append(0.0)
    else:
        top = candidates[0]
        score = min(100.0, top.score * 20)
        if top.label == "ramping":
            score = min(100.0, score + 10)
        readiness_scores.append(score)

backup_readiness_pct = round(mean(readiness_scores)) if readiness_scores else None
```

---

## Backend requirements

### 1. Service function

In `backend/app/services/kra_metrics.py`:

```python
def compute_backup_readiness(
    db: Session,
    tenant_id: uuid.UUID,
) -> BackupReadinessResult:
    ...
```

```python
class SpofBackupRow(BaseModel):
    component_id: str
    component_name: str
    primary_owner_id: str | None
    primary_owner_name: str | None
    readiness_score: int              # 0-100 per component
    top_backup: EraBackupCandidate | None
    has_assigned_backup: bool         # from Assignment table if explicit backup role exists

class BackupReadinessResult(BaseModel):
    readiness_pct: int | None
    spof_count: int
    components: list[SpofBackupRow]
    unready_count: int                # spofs with readiness_score < 40
    data_completeness: KraMetricCoverage
```

Reuse `EraBackupCandidate` schema from `app.schemas.era` — do not duplicate.

### 2. Cognee integration

**Summary:** No Cognee LLM — use `find_backup_candidates` (SQL + telemetry).

**Evidence on drill-down:** For each `SpofBackupRow`, optional graph evidence:

```
Query: "Who else has contributed to {component_name} besides {primary_owner_name}?"
# tenant_graph_search, top_k=5 — narrative only, cached 1h
```

**Graph edges used implicitly:** `contributedTo`, `modifies`, review network — already in ingest.

### 3. Assigned backup detection

Check `Assignment` table for non-primary owner with `codebase_share_pct >= 15` on SPOF component → `has_assigned_backup=True`, boost component readiness by +15 (cap 100).

### 4. API

Extend `GET /api/analytics/kra/summary`:

```json
{
  "backup_readiness": {
    "readiness_pct": 34,
    "spof_count": 5,
    "unready_count": 4,
    "components": [...],
    "data_completeness": { "github": "confirmed" }
  }
}
```

### 5. Degradation

| Condition | Behavior |
|-----------|----------|
| No GitHub sync | Use assignment-only owners; backup score from assignment breadth only; flag `partial` |
| No SPOFs | `readiness_pct=100`, `spof_count=0` |
| No owners on SPOF | `readiness_score=0` for that component |

---

## Frontend requirements

### 1. KPI card

```
👥 Backup readiness    34%    → Assign backups
```

Color: red &lt;40%, amber 40–70%, green &gt;70%.

### 2. SPOF backup table

| Component | Primary owner | Top backup | Score | Action |
|-----------|---------------|------------|-------|--------|
| Payments | Alex (82%) | Jordan (ramping, 3.2) | 74 | Assign |
| Auth | Sam (91%) | — | 0 | Assign |

- "Assign" opens existing KRA side drawer backup form (`assignKraBackup`)
- Show `ramping` / `secondary` badge on backup name

### 3. ERA cross-link

From ERA employee detail affected components → "View backup plan in KRA" deep link with `?component={id}`.

---

## Tests

`backend/tests/test_kra_backup_readiness.py`:

- [ ] SPOF with strong backup candidate → high component score
- [ ] SPOF with no candidates → score 0
- [ ] Ramping label → +10 bonus applied
- [ ] Assigned backup in DB → `has_assigned_backup=True`, score boost
- [ ] No SPOFs → readiness_pct=100
- [ ] Org average matches manual mean of component scores

---

## Files to touch

| File | Action |
|------|--------|
| `backend/app/services/kra_metrics.py` | Add `compute_backup_readiness` |
| `backend/app/schemas/kra.py` | Add `BackupReadinessResult`, `SpofBackupRow` |
| `backend/app/services/cognee_era_intelligence.py` | Export/reuse `find_backup_candidates` (no logic change unless needed) |
| `backend/app/routes/analytics.py` | Extend summary |
| `frontend/src/components/kra/KraDashboard.tsx` | Readiness KPI + SPOF table |
| `frontend/src/components/kra/KraSideDrawer.tsx` | Wire assign flow from table (if split) |
| `frontend/src/lib/types.ts`, `api.ts` | Types + fetch |

---

## Exit criteria

- [ ] Org backup readiness % visible on `/kra`
- [ ] Each SPOF shows named top backup or explicit "None"
- [ ] Assign backup flow reachable from readiness table
- [ ] Scores match `find_backup_candidates` output in tests
- [ ] No Cognee LLM on summary endpoint

## Out of scope

- Auto-assigning backups without manager action
- ML prediction of backup success
- Changing backup weight constants (use existing 0.4/0.35/0.25)
