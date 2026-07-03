# KRA — Knowledge Risk Assessment

**Route:** `/kra`  
**Audience:** Engineering managers, staff engineers, platform leads  
**Centricity:** System — *where* knowledge is trapped

**Companion:** ERA is person-centric ("who is at risk?"); KRA is system-centric ("what breaks if they leave?").

> **Implementation prompts:** Repo `prompts/kra/00_product_design.md` through `05_blast_radius_narrative.md`

---

## Problem statement

Organizations lose velocity when critical system knowledge lives in one engineer's head, stale Notion pages, or buried Slack threads. KRA surfaces **actionable structural risk** before attrition, repeat incidents, or audit failure.

---

## Design principles

| Principle | Rule |
|-----------|------|
| **Component-first** | Every metric anchors on `Component`, not `Employee` |
| **Deterministic scores** | Metrics 1–4: SQL + telemetry + graph edge counts — no LLM for numbers |
| **Cognee for graph + narrative** | `GRAPH_COMPLETION` only for drill-down and Metric 5 |
| **Honest degradation** | Missing integration → partial badge or hide metric |
| **Manager speed** | Summary &lt;500ms; story in &lt;30 seconds |
| **ERA cross-link** | ERA KPIs deep-link into KRA filters |

---

## Cognee role

```
Integration sync → Cognee ingest → Knowledge graph (tenant-scoped)
                                        │
                    documentedBy, contributedTo, dependsOn
                    resolvedOn (Slack), blocksComponent (Jira)
                                        │
        Metrics 1–4: graph edges + SQL (no LLM on summary)
        Metric 5 + drill-down: GRAPH_COMPLETION (cached ~1h)
```

**Never:** `search("how many SPOFs?")` → count  
**Always:** `bus_factor <= 1 AND criticality = tier1_revenue` → count; Cognee explains *why* on click.

---

## Five metrics

| # | Metric | Question | Type |
|---|--------|----------|------|
| 1 | **Critical SPOF Count** | Revenue-critical systems with no backup owner? | Count |
| 2 | **Documentation Coverage** | % of actively shipped systems with fresh runbooks? | % |
| 3 | **Incident Knowledge Debt** | Systems with repeat incidents, no doc updates? | Count |
| 4 | **Backup Readiness Index** | For SPOFs, someone could take over in days? | % |
| 5 | **Blast Radius Narrative** | If this fails, what else breaks? | Story (Cognee) |

### Severity colors

| Signal | Red | Amber | Green |
|--------|-----|-------|-------|
| Critical SPOFs | n &gt; 0 | — | n = 0 |
| Doc coverage | &lt;50% | 50–79% | ≥80% |
| Incident debt | n &gt; 0 | — | n = 0 |
| Backup readiness | &lt;40% | 40–70% | &gt;70% |

---

## User experience

### Summary strip (top of `/kra`)

```
[Critical SPOFs: 3] [Doc coverage: 62%] [Incident debt: 4] [Backup readiness: 34%]
```

### Interaction model

1. Land on component graph (nodes = components + owners)
2. KPI strip shows org health
3. Click KPI → filtered list or side panel
4. Click component → detail drawer with blast radius + per-component flags

---

## API contract

| Method | Path | Returns |
|--------|------|---------|
| `GET` | `/api/analytics/kra` | Graph nodes/edges |
| `GET` | `/api/analytics/kra/summary` | All 4 numeric metrics + optional featured narrative |
| `GET` | `/api/analytics/kra/components/{id}` | Blast radius + component snapshot |
| `POST` | `/api/analytics/kra/assign-backup` | Assign backup owner |

Summary cache: ~5 min in-memory per tenant.

---

## Integration requirements

| Integration | Metrics | If missing |
|-------------|---------|------------|
| GitHub | 1, 2, 4 | Assignment-only owners; `partial` badge |
| Notion | 2, 3 | Hide or degrade doc coverage |
| Slack | 3 | Jira-only incident debt |
| Jira | 3, 5 | Slack-only incidents |

---

## ERA vs KRA

| ERA | KRA |
|-----|-----|
| Employee risk score | Component structural risk |
| Burnout, task load | Bus factor, doc gaps |
| "Who might leave?" | "What breaks if they do?" |
| Person detail hero | Component blast radius |

---

## Success criteria

- [ ] Manager answers "where is knowledge trapped?" without opening GitHub/Notion
- [ ] Every number reproducible from telemetry (tests prove formulas)
- [ ] Cognee failure never breaks summary load
- [ ] Partial integration state visible
- [ ] One click from ERA SPOF KPI → KRA filtered view

---

## Related

- [ERA design](./01-era.md)
- [Integrations](./06-integrations-platform.md)
- [Runbook: integration sync](../runbooks/02-integration-sync.md)
