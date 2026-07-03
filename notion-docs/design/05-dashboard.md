# Manager Dashboard

**Route:** `/dashboard`  
**Audience:** Engineering managers

---

## Purpose

The manager **cockpit** — aggregate org health at a glance and entry point to deeper modules (ERA, KRA, II).

Post-login default landing page (after onboarding complete).

---

## Key metrics

| Metric | Source | Module tie-in |
|--------|--------|---------------|
| **Employee count** | PostgreSQL `employees` | Org chart |
| **Average tenure** | `tenure_years` aggregate | Onboarding / Notion directory |
| **Open incidents** | `incident_records` (non-Resolved/Closed) | II |
| **Active SPOFs** | KRA graph nodes with `is_spof=true` | KRA |
| **Attrition rate** | Placeholder / future HR integration | — |

API: `GET /api/dashboard/metrics` → `DashboardMetrics` schema.

---

## Setup checklist

Onboarding-adjacent checklist on dashboard surfaces integration gaps:

| Integration | Unlocks |
|-------------|---------|
| GitHub | Code ownership, DOA, file risk |
| Jira | Incidents, sprint load, II gate |
| Notion | Directory, runbooks, doc coverage |
| Slack | On-call, incident threads |

Each item links to `/settings` integration config.

---

## Digest settings

`WorkspaceContext` stores digest preferences (localStorage):

- Frequency and module highlights
- Cross-module notification hooks (e.g. incident resolved → refresh metrics)

---

## Real-time updates

| Event | Behavior |
|-------|----------|
| Incident resolved in II | `notifyIncidentResolved()` → decrement open count optimistically |
| Integration sync complete | `refreshMetrics()` on return to dashboard |
| ERA/KRA navigation | Metrics are point-in-time; modules show live detail |

---

## UI components

| Component | Role |
|-----------|------|
| `DashboardPage` | Layout, metric cards |
| Metric cards | Click-through to ERA / KRA / II |
| Setup checklist | Integration status badges |

---

## Future enhancements (deferred)

- Weekly digest email
- Trend sparklines (ERA step 11 rollups)
- Team-level risk roll-up from ERA command center

---

## Related

- [Platform overview](./00-platform-overview.md)
- [Onboarding & auth](./07-onboarding-auth.md)
- [Runbook: local development](../runbooks/01-local-development.md)
