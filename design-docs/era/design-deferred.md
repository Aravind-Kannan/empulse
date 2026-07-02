# ERA — Deferred Improvements (Post–v1)

Features identified from industry references that are **feasible in principle** but **out of scope for the current ERA implementation plan**. Pick these up after Steps 01–18 ship and ERA is fully functional in production.

See [README.md](./README.md) for the active plan and [design-improvements.md](./design-improvements.md) for what is already in scope.

---

## Deferred items

| ID | Feature | Source | Why deferred | Prerequisite |
|----|---------|--------|--------------|--------------|
| D1 | **DX surveys / DXI (Developer Experience Index)** | [DX](https://getdx.com/) | Different product surface — qualitative surveys, not continuity risk from system signals | Stable ERA + opt-in survey module |
| D2 | **Developer leaderboards / individual commit rankings** | CodePulse, Pluralsight Flow | Conflicts with non-surveillance ethics; erodes trust with ICs | N/A — reconsider only if policy changes |
| D3 | **R&D capitalization / DevFinOps reporting** | [Jellyfish](https://jellyfish.co/) | Finance buyer, Jira taxonomy discipline, different KPIs | Mature Jira investment labels |
| D4 | **External industry benchmark bands** | Jellyfish, DX | Requires large anonymized dataset; internal baselines (Step 11) sufficient for v1 | Multi-tenant analytics at scale |
| D5 | **Investment allocation overlay (% feature vs maintenance)** | Jellyfish | Needs epic/initiative hygiene in Jira; high process dependency | D3 or consistent Jira model |
| D6 | **M&A / due diligence export mode** | ContributorIQ | PDF/report pack for acquirers — valuable but niche | ERA + KRA stable, export pipeline |
| D7 | **Knowledge-loss ROI calculator** | WorkFera | Executive slide tool; not core to scoring accuracy | Validated ERA in customer pilots |
| D8 | **Full AI “Knowledge Clone” interviews** | WorkFera | Overlaps Investigation + Cognee Q&A; heavy AI/product scope | Step 10 + Exit bridge proven |
| D9 | **Individual commit activity timelines** | Pluralsight Flow | Surveillance risk; marginal value over team-level signals | N/A unless admin-only debug |
| D10 | **PagerDuty/Opsgenie deep integration** | Ops tools | On-call rotation API adds vendor scope; Slack bot parsing covers v1 | Customer demand for PD |

---

## When to revisit

| Trigger | Consider enabling |
|---------|-------------------|
| EM asks “how do we compare to industry?” | D4 internal-first, then external if data exists |
| Finance needs R&D tax / capitalization | D3, D5 |
| Acquisition diligence | D6 |
| HR wants attrition *prediction* not continuity | D1 (DX) as separate module, not merged into ERA % |
| Customers want WorkFera-style exit interviews | D8 as Exit module v2 |

---

## Effort rough-order (when picked up)

| ID | Estimate |
|----|----------|
| D1 | 3–4 weeks |
| D3 + D5 | 4–6 weeks |
| D4 | 2–4 weeks (internal); 8+ weeks (external) |
| D6 | 1–2 weeks |
| D7 | 3–5 days |
| D8 | 4–8 weeks |
| D10 | 1–2 weeks |
