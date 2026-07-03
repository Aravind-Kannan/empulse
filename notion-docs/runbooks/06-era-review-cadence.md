# Runbook: ERA Review Cadence

**Owner:** Engineering managers  
**When:** Monthly (or after major org/integration change)  
**Reference:** Repo `design-docs/era/step-17-alerts-review-cadence.md`

---

## Purpose

Structured ritual to review continuity risk, act on mitigations, and prevent silent knowledge concentration.

**Time box:** 30–45 minutes per team

---

## Pre-meeting checklist

| Task | Owner |
|------|-------|
| All integrations synced in last 7 days | EM |
| Identity mappings reconciled (no unmapped banner) | EM + IC leads |
| ERA command center loaded (`/era`) | EM |
| KRA summary reviewed (`/kra`) | EM |

---

## Agenda

### 1. Top risks (10 min)

Open `/era` command center:

- Sort by risk score descending
- Identify **top 3** employees above threshold (suggest: ≥60% or team-defined)
- For each: read top evidence item — can you explain the score in one sentence?

### 2. SPOF cross-check (5 min)

Open `/kra` summary strip:

- Critical SPOF count > 0? → click through to affected components
- Cross-link ERA top risks — do SPOF owners overlap?

### 3. Unmapped activity (5 min)

If ERA shows unmapped banner:

- Assign owner to reconcile identity mappings before next review
- Do not discuss risk scores for unmapped telemetry

### 4. Mitigations (10 min)

For each top-risk employee with open mitigations:

| Question | Action |
|----------|--------|
| Still open from last month? | Escalate or re-prioritize |
| Backup assigned? | Use KRA assign-backup or manual pairing |
| Doc gap flagged? | Create Notion runbook ticket |

### 5. Incidents loop (5 min)

Open `/kra` → Incident Knowledge Debt:

- Any component with repeat incidents + stale docs?
- Link to II resolved incidents — was postmortem written?

### 6. Exit readiness (5 min)

For anyone on departure watchlist (high B dimension):

- Confirm handover pack path: `/exit?prefill=era`
- Pre-draft successor from ERA backup candidates

---

## Outputs (document in Notion)

| Output | Template |
|--------|----------|
| Risk register snapshot | Top 3 names + one-line reason + score |
| Open mitigations | Checklist with owners + due dates |
| SPOF action items | Component → backup assignee |
| Identity debt | Count of unmapped activities + owner |
| Next review date | Calendar invite |

---

## Thresholds (suggested defaults)

| Signal | Action |
|--------|--------|
| ERA ≥ 70% | Mandatory mitigation plan within 2 weeks |
| Critical SPOF > 0 | Staff engineer review within 1 week |
| Doc coverage < 50% | Runbook sprint for top 3 gap components |
| Backup readiness < 40% | Pair programming / shadowing assignment |
| Unmapped activity > 10 events | Block risk decisions until reconciled |

Customize per org in Settings or team playbook.

---

## When to run ad-hoc

- Major reorg or manager change
- Key person announces departure
- Post-incident (severity ≥ SEV-2)
- New revenue-critical component shipped
- After first GitHub/Notion full sync

---

## Related

- [ERA design](../design/01-era.md)
- [KRA design](../design/02-kra.md)
- [Employee Exit](../design/04-employee-exit.md)
- ERA step 17: alerts + review cadence implementation
