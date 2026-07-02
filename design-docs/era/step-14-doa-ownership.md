# Step 14 — DOA Ownership & Knowledge Decay

**Depends on:** 01, 04 (live GitHub sync pipeline)  
**Blocks:** 13, 15; upgrades K dimension in 02  
**Estimate:** 5–8 days  
**Reference:** [ContributorIQ — Degree of Authorship](https://contributoriq.com/blog/degree-of-authorship-code-ownership-explained)

## Goal

Replace naive LOC % with **Degree of Authorship (DOA)** (Fritz et al.) for code ownership and bus-factor calculation.

## DOA model (per contributor, per file)

Factors:

1. **First authorship (FA)** — created the file
2. **Deliveries (DL)** — modification count by contributor
3. **Acceptances (AC)** — changes by others since contributor’s last edit (knowledge decay)

Normalized score `0.0–1.0`. Contributor with **DOA > 0.75** = authoritative author on that file.

## Bus factor (repo/component level)

Minimum set of authors (DOA > 0.75) needed to cover >50% of files in scope.

| Bus factor | Risk level |
|------------|------------|
| 1 | Critical |
| 2 | High |
| 3–4 | Medium |
| 5+ | Low |

## Knowledge decay signal

Per employee + file:

```
decay = changes_by_others_since_last_touch / total_changes_since_last_touch
```

High decay + high historical DOA → evidence: “You haven’t touched this file in N months despite M team edits.”

## Integration with Step 02 (K dimension)

```python
# Prefer max DOA across owned files over LOC %
k_signal = max(doa_per_file for file in owned_paths) * 100
# Weight by component criticality tier
```

## Storage

```python
class DoaFileSnapshot(Base):
    tenant_id, component_id, file_path, employee_id
    doa_score: float
    is_author: bool          # doa > 0.75
    last_touch_at: datetime
    decay_score: float
    computed_at: datetime
```

Compute on GitHub sync; scope to assigned components + `path_component_map` to limit API cost.

## Performance

- Window: 6 months default
- Cap files per component: top 500 by churn
- Incremental: only recompute files touched in last sync

## Edge cases

| Case | Handling |
|------|----------|
| Squash merges | Attribute to PR author |
| Co-authored commits | Split or primary author only (config) |
| Large binary files | Exclude from DOA |
| Submodule / vendored | Exclude paths |

## Exit criteria

- [ ] `codebase_share_pct` derived from DOA footprint where GitHub connected
- [ ] Bus factor per component on KRA
- [ ] Evidence cites DOA score, not just LOC

## Files to touch

- `backend/app/services/github_doa.py` — new
- `backend/app/services/integration_telemetry.py` — use DOA for ownership
- `backend/app/services/cognee_era_metrics.py`
- `backend/app/services/era/dimensions.py` (Step 02)
