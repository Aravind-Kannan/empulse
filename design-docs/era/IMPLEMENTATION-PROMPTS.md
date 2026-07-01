# ERA Implementation Prompts & Verification Plan

Ordered prompts for implementing ERA Steps 01–18. Matches the build order in [README.md](./README.md).

**Global prefix (optional — prepend to any prompt):**

> Read `design-docs/era/step-XX-*.md` and `design-docs/era/employee-risk-assessment.md`. Follow existing Empulse patterns (thin routes, services layer, dark UI). Do not implement items in [design-deferred.md](./design-deferred.md).

---

## Phase A — Foundation

### Step 01 — Identity foundation

**Prompt:**

```
Implement ERA Step 01 (Identity Foundation) per design-docs/era/step-01-identity-foundation.md:
- Add resolve_employee() with confidence levels (confirmed/high/medium/none)
- Add UnmappedActivity model and quarantine queue
- Gate integration_sync and integration_telemetry so unmapped events are never attributed
- Extend /api/identity with unmapped_count and GET /api/identity/unmapped
- Add unit tests for attribution edge cases
```

**Verify:**

| Check | How |
|-------|-----|
| DB migration applies | `unmapped_activities` table exists |
| Mapped event attributes | Unit test: confirmed mapping → correct `employee_id` |
| Unmapped quarantined | Unit test: unknown GitHub user → `UnmappedActivity`, not counted on anyone |
| API | `GET /api/identity/reconciliation` returns `unmapped_count` |
| No regression | `POST /api/integrations/sync/github` still completes |

---

### Step 02 — Scoring engine

**Prompt:**

```
Implement ERA Step 02 (Scoring Engine) per design-docs/era/step-02-scoring-engine.md:
- Create backend/app/services/era/ package with K/O/D/S/B dimension calculators
- Add Component.criticality tier, role weight profiles, tenure modifier, tenant percentile normalization
- Wire get_era_metrics() behind feature flag ERA_V2_SCORING
- Keep legacy EraEmployeeMetrics fields populated for backward compatibility
- Add golden-file unit test for Alice walkthrough (~58% medium)
```

**Verify:**

| Check | How |
|-------|-----|
| Unit tests pass | `pytest backend/app/services/era/` |
| Feature flag off | Old formula still works when `ERA_V2_SCORING=false` |
| Feature flag on | Returns `dimensions` object per employee |
| Leadership excluded | Leadership roles not in ERA list |
| Evidence | Top 5 `EraEvidenceItem` generated per employee (mock signals ok) |

---

### Step 03 — Evidence API contract

**Prompt:**

```
Implement ERA Step 03 (Evidence API Contract) per design-docs/era/step-03-evidence-api-contract.md:
- Extend GET /api/analytics/era with team_summary, sync_freshness, demo_mode, warnings, unmapped_activity
- Extend EraEmployeeMetrics with dimensions, evidence[], affected_components, identity_coverage, data_completeness_pct
- Add GET /api/analytics/era/{employee_id} for full evidence list
- Mirror types in frontend/src/lib/types.ts and update fetchEraMetrics in api.ts
```

**Verify:**

| Check | How |
|-------|-----|
| OpenAPI | Visit `http://localhost:8000/docs` — schema shows new fields |
| curl | `curl localhost:8000/api/analytics/era` returns `team_summary` + `dimensions` |
| Detail endpoint | `curl localhost:8000/api/analytics/era/{id}` returns full evidence |
| Frontend types | `npm run build` in frontend passes |
| Backward compat | Existing `EraDashboard` still renders with legacy fields |

---

## Phase B — UI shell (can use mock API)

### Step 08 — Command center UI

**Prompt:**

```
Implement ERA Step 08 (UI Command Center) per design-docs/era/step-08-ui-command-center.md:
- Create EraCommandCenter and child components (KpiStrip, RiskHeatmap, EmployeePreview, TeamComposition, EvidenceFeed)
- Replace or feature-flag EraDashboard on /era page
- Consume API v2 team_summary and dimensions; skeleton/empty/error states
- KPI strip, 5-dimension heatmap, evidence feed; link SPOF chips to /kra
```

**Verify:**

| Check | How |
|-------|-----|
| Page loads | `http://localhost:3000/era` — no console errors |
| KPI strip | 6 cards show values from `team_summary` |
| Heatmap | Rows show K/O/D/S/B mini-bars + risk % |
| Interaction | Row click updates preview panel |
| Demo mode | Amber border when `demo_mode: true` |
| Responsive | Usable at 1280px and mobile card layout |
| Manual | Identify top 3 risks in <5 seconds |

---

## Phase C — Connectors + Git intelligence

### Step 04 — GitHub telemetry

**Prompt:**

```
Implement ERA Step 04 (GitHub Telemetry) per design-docs/era/step-04-github-telemetry.md:
- Replace MOCK_GITHUB_ACTIVITY with live GitHub API client
- Persist ownership snapshots to DB; wire apply_github_telemetry from real data
- Map file paths to components; ingest GraphPullRequest to Cognee on sync
- Generate evidence with real PR URLs
```

**Verify:**

| Check | How |
|-------|-----|
| Sync | `POST /api/integrations/sync/github` succeeds with real token |
| Telemetry | Telemetry snapshot shows `github_synced: true` |
| ERA updates | `codebase_share_pct` changes after sync vs Acme fallback |
| Evidence URLs | Evidence `sources[].url` opens real GitHub PR |
| Quarantine | Unmapped GitHub author → unmapped queue (Step 01) |

---

### Step 14 — DOA ownership

**Prompt:**

```
Implement ERA Step 14 (DOA Ownership) per design-docs/era/step-14-doa-ownership.md:
- Add github_doa.py with Fritz et al. DOA model per file
- Compute bus factor per component; knowledge decay signal
- Hook into GitHub sync; replace LOC-only ownership in K dimension when DOA available
- Store DoaFileSnapshot; update evidence to cite DOA scores
```

**Verify:**

| Check | How |
|-------|-----|
| DOA computed | DB rows in `doa_file_snapshots` after sync |
| K dimension | Evidence mentions DOA % not just LOC |
| Bus factor | KRA or API exposes bus factor per component |
| Performance | Sync completes within reasonable time (scoped to owned components) |

---

### Step 15 — Review network & risky changes

**Prompt:**

```
Implement ERA Step 15 per design-docs/era/step-15-review-network-risky-changes.md:
- Add github_reviews.py: review network graph, review_concentration, risky PR detection
- Feed backup_review_score in K dimension (Step 02)
- Add GET /api/analytics/era/{id}/review-network and team risky-changes endpoint
- Evidence: "No backup reviewer on last N PRs" with links
```

**Verify:**

| Check | How |
|-------|-----|
| Review data | API returns reviewers for a test employee |
| K score | `backup_review_score` reflects real review data |
| Risky PRs | Merged-without-review PR appears in team feed |
| UI placeholder | Optional: mini graph on ERA detail (Step 09 can consume later) |

---

### Step 05 — Jira telemetry

**Prompt:**

```
Implement ERA Step 05 (Jira Telemetry) per design-docs/era/step-05-jira-telemetry.md:
- Replace MOCK_JIRA_ISSUES with live Jira REST/JQL client
- Per-employee open_tasks, jira_backlog_boost, epic ownership
- Update Component.open_tasks_count and unresolved_incidents from Jira
- Evidence links to Jira issue URLs
```

**Verify:**

| Check | How |
|-------|-----|
| Sync | `POST /api/integrations/sync/jira` succeeds |
| `has_jira_sync()` | true in telemetry snapshot |
| ERA | `open_tasks`, `jira_backlog_boost` reflect real issues |
| Unassigned P1 | Boost attributed to component main engineer |

---

## Phase D — UI depth + matrix

### Step 09 — Employee detail

**Prompt:**

```
Implement ERA Step 09 per design-docs/era/step-09-ui-employee-detail.md:
- EraDetailDrawer slide-over from command center
- Hero with risk ring, dimension grid, radar chart, full evidence list
- Affected components mini-graph; deep link /era?employee={id}
- Footer: identity coverage, sync freshness, export
```

**Verify:**

| Check | How |
|-------|-----|
| Open drawer | Click employee row → drawer opens |
| Deep link | `/era?employee=emp-xxx` opens drawer on load |
| Evidence | All items from detail API visible with source links |
| Dimensions | 5 cards match API `dimensions` values |
| KRA link | Click component → navigates to KRA |

---

### Step 13 — File risk matrix

**Prompt:**

```
Implement ERA Step 13 per design-docs/era/step-13-file-risk-matrix-hotspots.md:
- Add github_file_risk.py and FileRiskSnapshot model
- Quadrant classification (critical/stable/active/healthy)
- GET /api/analytics/kra/file-risk and employee hotspots endpoint
- FileRiskMatrix on KRA; EraHotspotSummary on ERA detail
- Critical files feed K dimension evidence
```

**Verify:**

| Check | How |
|-------|-----|
| API | File risk returns files with quadrant labels |
| KRA UI | Matrix renders for a component with GitHub data |
| ERA evidence | High-severity item for critical-quadrant file |
| Exclusions | Test/vendor paths not flagged |

---

## Phase E — Notion + Slack

### Step 06 — Notion telemetry

**Prompt:**

```
Implement ERA Step 06 per design-docs/era/step-06-notion-telemetry.md:
- Add notion to process_external_app_sync
- Doc inventory, staleness, documentedBy Cognee edges
- Living runbook / ownership transfer Notion template support
- Replace synthetic _undocumented_solved_incidents when Notion connected
- Guru-style expertise tags from People DB if present
```

**Verify:**

| Check | How |
|-------|-----|
| Sync | Notion sync completes with integration token |
| Doc gaps | Component with code activity but no Notion page → D evidence |
| Stale runbook | `last_edited` > 180d → stale evidence |
| KRA | Real doc sources replace mock DOCUMENTATION_SOURCES |
| Cognee | documentedBy edges queryable |

---

### Step 07 — Slack telemetry

**Prompt:**

```
Implement ERA Step 07 per design-docs/era/step-07-slack-telemetry.md:
- Add slack_client.py and process_external_app_sync("slack")
- Incident resolution heuristic; undocumented vs Notion cross-check
- On-call incident counts; escalation/shadow routing signal for S dimension
- Evidence with Slack thread URLs (counts only in UI, not message bodies)
```

**Verify:**

| Check | How |
|-------|-----|
| Sync | Slack sync with configured incident channels |
| D dimension | Real `undocumented_solved_incidents` when Slack+Notion connected |
| Escalation | Repeated @mentions → S dimension evidence |
| Privacy | Dashboard shows thread titles/links, not full message content |

---

## Phase F — Intelligence & workflow

### Step 10 — Cognee intelligence

**Prompt:**

```
Implement ERA Step 10 per design-docs/era/step-10-cognee-intelligence.md:
- Add cognee_era_intelligence.py: backup candidates, blast radius, evidence enrichment
- Rank backups with DOA + review participation (Step 14/15); "ramping" label
- On-demand Cognee queries on employee detail only; degrade gracefully if Cognee down
```

**Verify:**

| Check | How |
|-------|-----|
| Detail API | Returns `backup_candidates[]` ranked |
| Cognee down | API 200 with `warnings: ["cognee_degraded"]` |
| Evidence | Graph-derived Jira links on evidence items where applicable |
| Performance | List endpoint `/api/analytics/era` does NOT call Cognee |

---

### Step 11 — Trends & rollups

**Prompt:**

```
Implement ERA Step 11 per design-docs/era/step-11-trends-and-rollups.md:
- EraRiskSnapshot model; snapshot job after sync
- trend_7d on employee metrics and team_summary
- Sparkline on KPI strip; 30d chart on detail drawer
- Optional manager roll-up endpoint
```

**Verify:**

| Check | How |
|-------|-----|
| Snapshot | Row created per employee per day after sync |
| Trend | `trend_7d` non-null after 2+ days of snapshots |
| UI | KPI strip shows ▲/▼ chip |
| Idempotent | Re-running snapshot same day upserts, not duplicates |

---

### Step 12 — Mitigations

**Prompt:**

```
Implement ERA Step 12 per design-docs/era/step-12-mitigations-actions.md:
- Mitigation rule engine; EraEvidenceMitigation model
- PATCH /api/analytics/era/evidence/{id} for status (open/in_progress/done/dismissed)
- EraMitigationChecklist on employee detail drawer
- Stable evidence IDs via hash(dimension + title + component_id)
```

**Verify:**

| Check | How |
|-------|-----|
| Rules | High-K employee gets "Add CODEOWNERS backup" suggestion |
| PATCH | Mark mitigation done → persists across refresh |
| Recompute | Evidence ID stable after ERA recompute |
| UI | Checklist shows open/done states |

---

### Step 16 — ERA → Exit bridge

**Prompt:**

```
Implement ERA Step 16 per design-docs/era/step-16-era-exit-bridge.md:
- Extend GET /api/exit/handover?prefill=era with ERA evidence sections
- Update exit_handover.py to include affected components, backups, open mitigations, hotspots
- "Start exit handover" button on ERA detail → /exit?employee=id&prefill=era
```

**Verify:**

| Check | How |
|-------|-----|
| API | `handover?prefill=era` markdown includes ERA sections |
| Navigation | Button from ERA detail opens Exit with pre-filled content |
| Mitigations | Open mitigations appear as checklist in markdown |
| Stale data | Handover header shows ERA `computed_at` |

---

### Step 17 — Alerts & review cadence

**Prompt:**

```
Implement ERA Step 17 per design-docs/era/step-17-alerts-review-cadence.md:
- EraAlert and EraTeamReview models; era_alerts.py rule engine
- GET/POST alerts and reviews endpoints
- EraAlertsBanner on command center; optional Slack webhook in settings
- Alerts to team channels only, not individual surveillance DMs
```

**Verify:**

| Check | How |
|-------|-----|
| Rules fire | Create SPOF on tier1 → alert appears |
| Acknowledge | POST acknowledge clears from unacknowledged list |
| Review | "Mark reviewed" records EraTeamReview |
| Banner | "Last review 47 days ago" shows when overdue |
| Webhook | Optional Slack POST on alert (settings toggle) |

---

### Step 18 — Orphans & org health

**Prompt:**

```
Implement ERA Step 18 per design-docs/era/step-18-orphan-files-org-health.md:
- github_orphans.py; org_health.py composite score
- org_health_score, orphan_file_count on team_summary
- Org health KPI on command center; orphan trend in snapshots (Step 11)
- Baseline orphan snapshot when Employee.active set false
```

**Verify:**

| Check | How |
|-------|-----|
| API | `team_summary.org_health_score` 0–100 |
| Orphans | Count increases when sole author marked inactive |
| UI | Org health card on KPI strip |
| Snapshots | `orphan_file_count` in team snapshot history |

---

## End-to-end verification (after Step 18)

**Acceptance checklist:**

```
[ ] Fresh tenant: onboarding → import org → reconcile identity → sync all 4 connectors
[ ] GET /api/analytics/era: demo_mode=false, data_completeness_pct > 80%
[ ] Command center: KPIs + heatmap + evidence feed populated
[ ] Top employee detail: 5 dimensions, evidence with GitHub/Jira/Notion/Slack links
[ ] KRA file matrix shows critical quadrant files
[ ] Mark mitigation done; start exit handover with prefill=era
[ ] Acknowledge alert; complete monthly risk review
[ ] trend_7d and org_health_score visible after 2+ sync days
[ ] Unmapped GitHub user in quarantine — not on any employee's score
```

**Smoke commands:**

```bash
# Backend
cd backend && pytest app/services/era/ -q
curl -s localhost:8000/api/analytics/era | jq '.team_summary, .employees[0].dimensions'

# Frontend
cd frontend && npm run build
# Manual: open http://localhost:3000/era
```

---

## Tips

1. **One step per agent session** — keeps diffs reviewable.
2. **Say “do not start Step N+1”** if you want strict scope.
3. After **Steps 03 and 08**, do a **UI review** before heavy connector work.
4. **Steps 04 + 14 + 15** can be combined in one session; verify each layer separately.
5. Point agents at [cursor.md](../../cursor.md) for repo conventions.

## Related docs

| Doc | Purpose |
|-----|---------|
| [README.md](./README.md) | Build order, estimates, dependencies |
| [employee-risk-assessment.md](./employee-risk-assessment.md) | Master design |
| [design-improvements.md](./design-improvements.md) | v2 changes + reference features |
| [design-deferred.md](./design-deferred.md) | Post–v1 follow-ups |
