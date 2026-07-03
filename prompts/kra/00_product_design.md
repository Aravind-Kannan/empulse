# Knowledge Risk Assessment (KRA) — Product Design

**Audience:** Engineering managers, staff engineers, platform leads  
**Route:** `/kra`  
**Companion:** ERA (`/era`) is **person-centric**; KRA is **system-centric**. ERA asks *who is at risk*; KRA asks *where knowledge is trapped*.

---

## Problem statement

Organizations lose velocity when critical system knowledge lives in one engineer's head, stale Notion pages, or buried Slack threads. KRA surfaces **actionable structural risk** before attrition, repeat incidents, or audit failure — not another vanity dashboard.

---

## Design principles

| Principle | Rule |
|-----------|------|
| **Component-first** | Every metric anchors on `Component`, not `Employee` |
| **Deterministic scores** | Metrics 1–4 use SQL + integration telemetry + graph **edge counts** — never Cognee LLM free-text for numbers |
| **Cognee for graph + narrative** | Ingest multi-hop relationships; use `GRAPH_COMPLETION` / `CHUNKS` only for drill-down evidence and Metric 5 narrative |
| **Honest degradation** | Missing GitHub / Notion / Slack / Jira → partial badge or hide metric; never fake 0% |
| **Manager speed** | Org summary loads in &lt;500ms; full story understandable in &lt;30 seconds |
| **ERA cross-link** | ERA KPIs deep-link into KRA filters; KRA does not duplicate person-level burnout scoring |

---

## Cognee role (easy mental model)

```
Integration sync (GitHub, Notion, Slack, Jira)
        │
        ▼
   Cognee ingest ──► Knowledge graph (tenant-scoped)
        │                    │
        │                    ├── documentedBy, contributedTo, dependsOn
        │                    ├── resolvedOn (Slack incidents)
        │                    └── blocksComponent ← Jira
        │
        ├── METRICS 1–4: read graph edges + SQL telemetry (no LLM on summary)
        │
        └── METRIC 5 + drill-down: tenant_graph_search / GRAPH_COMPLETION (cached 1h)
```

**Never:** `search("how many SPOFs?")` → count  
**Always:** `bus_factor <= 1 AND criticality = tier1_revenue` → count; Cognee explains *why it matters* on click.

Reference implementation patterns: `backend/app/services/tenant_cognee.py`, `cognee_ingest.py`, `cognee_era_intelligence.py`, `design-docs/era/step-10-cognee-intelligence.md`.

---

## The five metrics (high impact only)

| # | Metric | One-line question | Type | Primary data | Cognee role |
|---|--------|-------------------|------|--------------|-------------|
| 1 | **Critical SPOF Count** | How many revenue-critical systems have no backup owner? | Count | GitHub bus factor, assignments, `criticality` | Evidence on drill-down (`ownsComponent` edges) |
| 2 | **Documentation Coverage** | What % of actively shipped systems have fresh runbooks? | % | Notion snapshots, GitHub activity, `documentedBy` | Ingest `documentedBy`; narrative on gap drill-down |
| 3 | **Incident Knowledge Debt** | Which systems repeat incidents without doc updates? | Count | Slack threads, Jira bugs, Notion `last_edited` | Optional `SlackIncident → resolvedOn → Component` ingest |
| 4 | **Backup Readiness Index** | For SPOFs, is there someone who could take over in days? | % | `find_backup_candidates()` (DOA + reviews + commits) | Graph validates `contributedTo` for evidence links |
| 5 | **Blast Radius Narrative** | If this fails, what else breaks? | Story | All of the above + graph dependencies | **Primary** Cognee `GRAPH_COMPLETION` (2–3 sentences, cited evidence) |

### Why these five (and not more)

- **SPOF count** — existential; board-level language ("3 revenue systems, one owner each")
- **Doc coverage** — cheapest fix before crisis; preventive
- **Incident debt** — closes II → runbook loop; proves learning culture
- **Backup readiness** — turns SPOF from binary panic into actionable ramping plan
- **Blast radius** — the only qualitative metric; makes numbers matter to non-technical leadership

Deferred (out of scope): file-level hotspot matrix (exists separately), person risk scores (ERA), auto-assign backups, numeric blast-radius score.

---

## User experience

### Summary strip (top of `/kra`)

```
[Critical SPOFs: 3] [Doc coverage: 62%] [Incident debt: 4] [Backup readiness: 34%]
```

Optional featured card below strip when Metric 1 &gt; 0:

> **Highest risk: Payments API** — "{cached blast radius teaser…}" [View details]

### Interaction model

1. Land on graph (components + owners)
2. KPI strip shows org health at a glance
3. Click KPI → filtered list or side panel
4. Click component node → detail drawer with Metric 5 narrative + per-component flags from 1–4

### Severity colors

| Signal | Red | Amber | Green |
|--------|-----|-------|-------|
| Critical SPOFs | n &gt; 0 | — | n = 0 |
| Doc coverage | &lt;50% | 50–79% | ≥80% |
| Incident debt | n &gt; 0 | — | n = 0 |
| Backup readiness | &lt;40% | 40–70% | &gt;70% |

---

## API contract (target state)

```
GET /api/analytics/kra              → graph (existing)
GET /api/analytics/kra/summary      → all 4 numeric metrics + optional featured_narrative
GET /api/analytics/kra/components/{id} → blast radius + component metric snapshot
POST /api/analytics/kra/assign-backup  → existing
```

Summary response shape:

```json
{
  "critical_spof": { "count": 3, "components": [...], "data_completeness": {...} },
  "documentation_coverage": { "coverage_pct": 62, "gap_components": [...] },
  "incident_knowledge_debt": { "count": 4, "components": [...] },
  "backup_readiness": { "readiness_pct": 34, "spof_count": 5, "components": [...] },
  "featured_narrative": { "component_id": "...", "component_name": "...", "narrative": "..." }
}
```

Cache: 5 min in-memory per tenant on summary (same pattern as `incident_feed`).

---

## Integration requirements

| Integration | Metrics powered | If missing |
|-------------|-----------------|------------|
| **GitHub** | 1, 2, 4 | Assignment-only owners; `partial` badge |
| **Notion** | 2, 3 | Hide doc coverage; incident debt degraded |
| **Slack** | 3 | Jira-only incidents |
| **Jira** | 3, 5 | Slack-only incidents |

---

## Implementation order

Feed these prompts to Cursor **in sequence**:

| Prompt | File | Delivers |
|--------|------|----------|
| 0 | `00_product_design.md` | This document — read first |
| 1 | `01_critical_spof_count.md` | Summary endpoint scaffold + first KPI |
| 2 | `02_documentation_coverage.md` | Doc coverage + `documentedBy` ingest |
| 3 | `03_incident_knowledge_debt.md` | Repeat-incident debt loop |
| 4 | `04_backup_readiness_index.md` | SPOF backup quality index |
| 5 | `05_blast_radius_narrative.md` | Component detail + Cognee narrative |

After prompt 5, `build_kra_summary()` returns all fields; component drill-down is the unified surface.

---

## Success criteria (product)

- [ ] Manager answers "where is knowledge trapped?" without opening GitHub or Notion
- [ ] Every number is reproducible from telemetry (tests prove formulas)
- [ ] Cognee failure never breaks summary load
- [ ] Partial integration state is visible, not hidden
- [ ] One click from ERA SPOF KPI → KRA filtered view

---

## Relationship to ERA

| ERA | KRA |
|-----|-----|
| Employee risk score | Component structural risk |
| Burnout, task load | Bus factor, doc gaps |
| "Who might leave?" | "What breaks if they do?" |
| Person detail hero | Component blast radius |

ERA may **read** KRA summary flags; KRA must not re-implement ERA person scoring.
