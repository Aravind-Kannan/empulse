# ERA Design Improvements (v1 → v2)

Summary of enhancements made during step-plan decomposition relative to the original [employee-risk-assessment.md](./employee-risk-assessment.md), with rationale and references to similar products.

---

## 1. Changes from the original design

### 1.1 Continuity risk vs departure probability (split framing)

**Original:** Burnout (B) dimension mixed *operational overload* with *likelihood to leave* in one score.

**Improved:** ERA composite score measures **continuity risk** (impact if they leave tomorrow). Burnout signals contribute as a **modifier** and separate **watchlist badge**, not as equal weight to knowledge concentration.

**Why better:** Products like [ContributorIQ](https://contributoriq.com/use-cases/departure-risk) and [WorkFera](https://www.workfera.com/solutions/knowledge-risk-review) separate *key-person dependency* from *attrition prediction*. Conflating them erodes trust when a burned-out engineer has low bus factor or a critical SPOF engineer appears “low risk” on workload.

---

### 1.2 Data completeness and confidence scoring

**Original:** `identity_coverage: Record<string, boolean>` — binary per provider.

**Improved:** Three-level coverage per provider (`confirmed` | `high` | `missing`), plus `data_completeness_pct` and dimension-level `partial` flags. Scores **renormalize weights** when a connector is absent.

**Why better:** A 72% risk score built from GitHub-only data should not look identical to one built from all four sources. [DX](https://getdx.com/) and [Jellyfish](https://jellyfish.co/) surface data-quality indicators alongside metrics so leaders know when to trust a number.

---

### 1.3 Unmapped activity quarantine queue

**Original:** “Reject unmapped activity” stated as a rule but no persistence model.

**Improved:** `UnmappedActivity` store + ERA header banner + reconciliation CTA. Events never attribute to a guessed employee.

**Why better:** Mis-attribution is worse than missing data. [WorkFera](https://www.workfera.com/solutions/knowledge-risk-review) emphasizes that invisible concentration is the failure mode — wrong concentration is actively harmful.

---

### 1.4 Team summary in one API response

**Original:** Dashboard sections described; no `team_summary` aggregate object.

**Improved:** `EraTeamSummary` with avg risk, high-risk count, SPOF count, open P1, undocumented incidents, `top_risk_driver`, and `estimated_recovery_weeks`.

**Why better:** Command-center UI (Step 08) needs **one request** for KPI strip + headline. Jellyfish-style exec dashboards lead with team-level rollups before drill-down.

---

### 1.5 Recovery time estimates (heuristic)

**Original:** Mentioned in employee headline example only.

**Improved:** Per-employee and team-level `recovery_estimate_weeks: { min, max }` derived from component count, SPOF flags, and documentation gap score.

**Why better:** Translates abstract % into planning language EMs use in staff meetings. [ContributorIQ](https://contributoriq.com/use-cases/departure-risk) outputs *knowledge transfer priority lists* with similar intent.

---

### 1.6 Component criticality weighting

**Original:** All components treated equally in ownership breadth.

**Improved:** Optional `Component.criticality` tier (`tier1_revenue` | `tier2_core` | `tier3_support`). K and O signals multiply by tier weight.

**Why better:** [ContributorIQ](https://contributoriq.com/use-cases/departure-risk) prioritizes *repository importance (revenue-critical first)*. 80% ownership of an internal tool ≠ 80% ownership of payments.

---

### 1.7 Tenant percentile normalization

**Original:** “Use percentiles within tenant” mentioned once.

**Improved:** Explicit normalization in Step 02 for unbounded signals (open tasks, message volume). Store raw + normalized.

**Why better:** A team with 5 open tasks may be healthy; another team’s p90 may be 3. Absolute thresholds don’t scale across org sizes.

---

### 1.8 Command Center UI as primary surface

**Original:** Extend existing table + side chart.

**Improved:** Dedicated **ERA Command Center** layout: KPI strip, risk heatmap, auto-selected top-risk preview, team composition donut, team-wide evidence feed.

**Why better:** [CodePulse](https://codepulsehq.com/features/knowledge-silos) uses a **risk matrix** (ownership × churn) for at-a-glance scanning. Table-only views hide dimensional patterns.

---

### 1.9 Evidence feed (team-wide)

**Original:** Evidence only on employee detail.

**Improved:** `EraEvidenceFeed` on command center — cross-employee stream of high-severity items.

**Why better:** Surfaces urgent items (unassigned P1, new SPOF) without clicking each row. Similar to incident feeds in PagerDuty / ops tools.

---

### 1.10 Mitigation state machine

**Original:** Static recommendation table.

**Improved:** `mitigation_status` on evidence items: `open` | `in_progress` | `done` | `dismissed` with assignee and due date.

**Why better:** [WorkFera](https://www.workfera.com/solutions/knowledge-risk-review) turns risk into a *fixable capture plan* on a cadence. Recommendations without tracking become shelfware.

---

### 1.11 Cross-training / backup candidates (first-class)

**Original:** Cognee query mentioned in passing.

**Improved:** Step 10 defines ranked backup candidates per component with ramping score (recent commits + review participation). Shown in employee detail.

**Why better:** [ContributorIQ](https://contributoriq.com/use-cases/departure-risk) identifies *successors: “Ramping Up” or secondary contributors*. Risk without mitigation path causes anxiety, not action.

---

### 1.12 `demo_mode` and sync freshness

**Original:** Not specified.

**Improved:** API returns `demo_mode`, `sync_freshness` per integration, and `warnings[]` for stale data (>24h).

**Why better:** Current codebase falls back to Acme mock data; UI must not present demo as production truth.

---

### 1.13 Ethics and naming

**Original:** Uses “bus factor” throughout.

**Improved:** User-facing copy prefers **continuity risk** / **key-person dependency**; internal docs may use bus factor. Avoid punitive framing in UI (“lottery factor” acceptable in tooltips).

**Why better:** HR and people managers reject morbid or blame-oriented language. [Laws of Software Engineering](https://lawsofsoftwareengineering.com/laws/bus-factor/) notes the term is intentionally provocative — fine for engineers, not for ERA dashboard titles.

---

## 2. What we kept from the original

- Five dimensions K/O/D/S/B and role-aware weights
- Email-first identity with manual reconciliation
- Cognee for multi-hop reasoning; SQL telemetry for fast ERA reads
- ERA (people) vs KRA (components) separation
- Evidence cards with source deep links
- Phased implementation (foundation → connectors → intelligence → actions)

---

## 3. Industry references and comparable products

### 3.1 Bus factor / key-person dependency (closest to ERA)

| Product | Focus | Relevant patterns for Empulse |
|---------|-------|-------------------------------|
| [ContributorIQ](https://contributoriq.com/use-cases/departure-risk) | Departure risk, DOA analysis, bus factor per repo | Contributor heatmaps, knowledge transfer priority lists, successor identification |
| [CodePulse](https://codepulsehq.com/features/knowledge-silos) | Bus factor 1 file detection, hotspot × ownership matrix | Risk matrix UI, cross-training priority ranking |
| [WorkFera](https://www.workfera.com/solutions/knowledge-risk-review) | Knowledge risk review, bus factor mapping | Live concentration map, ranked capture plan, cadence-based review |
| [Kinlyze](https://kinlyze.com/) (ecosystem) | Engineering knowledge graphs | Graph-based ownership visualization |
| [BusFactor.io](https://busfactor.io/) | GitHub bus factor calculator | Simple repo-level bus factor (Empulse goes wider: people + ops + docs) |

### 3.2 Engineering management / intelligence (partial overlap)

| Product | Focus | What to borrow |
|---------|-------|----------------|
| [Jellyfish](https://jellyfish.co/) | Engineering investment, allocative metrics, deliverables | Executive KPI strip, team roll-ups, investment-aligned component tiers |
| [DX (getdx.com)](https://getdx.com/) | Developer experience, surveys + system metrics | Data confidence indicators, trend deltas, benchmark context |
| [Pluralsight Flow](https://www.pluralsight.com/product/flow) | Git activity, code metrics | Contributor timelines (use carefully — avoid surveillance framing) |
| [Swarmia](https://www.swarmia.com/) | DevEx, workflow, team health | Team health dashboards, actionable insights linked to work items |
| [LinearB](https://linearb.io/) | Engineering metrics, team analytics | Metric breakdowns with clear “why” tooltips |

### 3.3 Knowledge management / offboarding

| Product | Focus | What to borrow |
|---------|-------|----------------|
| [Guru](https://www.getguru.com/) | Knowledge base, expert verification | “Who knows this?” expert tags → maps to K dimension |
| [Confluence + Atlas**]** | Docs + projects | Doc ownership and staleness signals for D dimension |
| [Offboard**]** (category) | Exit checklists | Mitigation checklist pattern in Step 12 |

### 3.4 Academic / conceptual

| Reference | URL | Relevance |
|-----------|-----|-----------|
| Bus Factor (Laws of Software Engineering) | https://lawsofsoftwareengineering.com/laws/bus-factor/ | Definition, knowledge-sharing mitigations |
| Truck factor / lottery factor | Common eng slang | Alternative UX copy |
| SHRM replacement cost research | Cited in industry blogs | Recovery week estimates order-of-magnitude |

### 3.5 Empulse differentiators

Empulse ERA should emphasize what generic bus-factor tools lack:

1. **Multi-source correlation** — Notion + Slack + Jira + GitHub via identity map (not Git-only)
2. **Cognee knowledge graph** — multi-hop “what breaks if X leaves?”
3. **Operational load** — open incidents, unassigned P1s, not just LOC
4. **Documentation gap** — Slack tacit knowledge vs Notion runbooks
5. **Unified cockpit** — ERA + KRA + Investigation + Exit in one product

---

## 4. Updated master design

The following sections were added to [employee-risk-assessment.md](./employee-risk-assessment.md):

- Link to this folder’s step plans
- Component criticality tier
- Data completeness model
- Continuity vs departure framing
- Team summary API fields
- Reference to external products (summary table)

See git history or compare Section 0 and Section 14 in the master design doc.

---

## 5. Reference features incorporated into the plan (Steps 13–18)

Feasible patterns from industry references, now part of the active implementation plan:

| Step | Feature | Reference | Rationale |
|------|---------|-----------|-----------|
| 13 | File risk matrix & hotspots | CodePulse | File-level churn × ownership; complements people heatmap |
| 14 | DOA ownership + knowledge decay | ContributorIQ | Research-backed ownership; replaces naive LOC % |
| 15 | Review network + risky changes | CodePulse | Real backup detection; system-level PR risk |
| 16 | ERA → Exit handover bridge | WorkFera | Unique Empulse loop; uses existing `/exit` module |
| 17 | Proactive alerts + review cadence | CodePulse, WorkFera | Push signals; monthly knowledge risk ritual |
| 18 | Orphan files + org health score | ContributorIQ | Post-departure risk; team resilience KPI |

### Also woven into existing steps

| Step | Addition | Reference |
|------|----------|-----------|
| 06 | Living runbooks, ownership transfer template, doc verification cadence | WorkFera |
| 07 | Escalation / shadow routing (incident @mention concentration) | WorkFera |
| 08 | Org health KPI, alerts banner, hotspot summary widget | ContributorIQ, CodePulse |
| 10 | Review-weighted backup candidates, “ramping” label | ContributorIQ |
| 06 | Notion expertise tags → K dimension | Guru |

---

## 6. Deferred to post–v1

Items **not** in Steps 01–18 — see [design-deferred.md](./design-deferred.md):

- DX surveys / DXI
- Developer leaderboards
- R&D capitalization / DevFinOps (Jellyfish)
- External industry benchmarks
- Investment allocation overlay
- M&A due diligence export
- Knowledge-loss ROI calculator
- Full AI Knowledge Clone interviews
- Individual commit surveillance timelines
- Deep PagerDuty integration

---

## 7. Time estimates

See [README.md](./README.md) for per-step and phased calendar estimates.

**Summary:** 73–103 developer-days total (~15–21 weeks @ 1 FTE, ~8–11 weeks @ 2 FTEs).
