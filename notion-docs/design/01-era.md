# ERA — Employee Risk Assessment

**Route:** `/era`  
**Audience:** Engineering managers, HR business partners  
**Centricity:** Person — *who* is at risk

> **Full specification:** Repo [`design-docs/era/employee-risk-assessment.md`](../../design-docs/era/employee-risk-assessment.md)  
> **Implementation steps:** Repo [`design-docs/era/README.md`](../../design-docs/era/README.md) (steps 01–18)

---

## Executive summary

**Employee Risk %** answers:

> If this person leaves tomorrow, how much operational and knowledge risk does the company take?

This is **not** a performance score. It is a **bus-factor / continuity score** built from correlated signals across connectors (Notion, Slack, GitHub, Jira), unified through an employee identity map, stored in Cognee as a knowledge graph, and aggregated into a **0–100% risk score with explainable evidence**.

### Continuity vs departure

| Concept | Meaning |
|---------|---------|
| **Composite ERA score** | Continuity risk — impact if unavailable tomorrow |
| **Burnout (B) dimension** | Overload signal; may show separate "departure watchlist" badge |

---

## Five risk dimensions

| Code | Dimension | Question | Primary sources |
|------|-----------|----------|-----------------|
| **K** | Knowledge concentration | Do they alone own critical code/docs? | GitHub, Notion, Cognee |
| **O** | Operational load | Unresolved work / incidents? | Jira, Slack, components |
| **D** | Documentation gap | Tacit knowledge undocumented? | Notion, Slack, incidents |
| **S** | Structural exposure | Bottleneck in org topology? | Org chart, assignments |
| **B** | Burnout / availability | Overloaded (departure indicator)? | Jira velocity, after-hours commits |

### Default IC weights

```
Risk% = min(100, Σ (dimension_score × role_weight))
```

| Dimension | Weight |
|-----------|--------|
| K — Knowledge | 35% |
| O — Operational | 25% |
| D — Documentation | 20% |
| S — Structural | 10% |
| B — Burnout | 10% |

Weights adjust by role (managers → higher S; on-call → higher O/B; new hires → tenure modifier).

---

## Component criticality

Not all ownership is equal:

| Tier | Label | K/O weight |
|------|-------|------------|
| `tier1_revenue` | Revenue-critical | 1.5× |
| `tier2_core` | Core platform | 1.0× |
| `tier3_support` | Internal / support | 0.6× |

---

## Data completeness

- Per-provider coverage: `confirmed` | `high` | `missing`
- `data_completeness_pct` per employee (0–100)
- Missing connectors → **weight renormalization** + `partial` flags
- Unmapped activity → **quarantine** (never guessed attribution)

---

## UI surfaces

| Surface | Purpose |
|---------|---------|
| Command center (`/era`) | Team table, risk breakdown, filters |
| Employee detail drawer | Evidence list, dimension scores, graph hops |
| Unmapped banner | Links to identity reconciliation |
| "Start exit handover" | Deep-link to `/exit?prefill=era` |

---

## Cross-module links

| From ERA | To |
|----------|-----|
| SPOF / owned components | KRA filtered view |
| High-risk employee | Exit handover pre-fill |
| Open mitigations | Exit checklist section |
| File hotspots | KRA / matrix views |

---

## Implementation roadmap (repo)

| Phase | Steps | Focus |
|-------|-------|-------|
| A Foundation | 01–03 | Identity, scoring, API contract |
| B UI shell | 08 | Command center |
| C Connectors | 04–05, 14–15 | GitHub, Jira, DOA, reviews |
| D Detail | 09, 13 | Drawer, file risk matrix |
| E Multi-source | 06–07 | Notion, Slack |
| F Intelligence | 10–12, 16–18 | Cognee, trends, mitigations, exit bridge |

See [`design-docs/era/README.md`](../../design-docs/era/README.md) for dependency graph and exit criteria.

---

## Success criteria

- [ ] Every risk point links to a source artifact
- [ ] Unmapped activity never silently mis-attributes
- [ ] Manager identifies top 3 at-risk people + reason in &lt;5 seconds
- [ ] ERA ↔ KRA ↔ Exit cross-linked
- [ ] `demo_mode` clearly distinguished from live data

---

## Related

- [KRA design](./02-kra.md) — system-centric complement
- [Employee Exit](./04-employee-exit.md) — handover bridge (step 16)
- [Runbook: ERA review cadence](../runbooks/06-era-review-cadence.md)
