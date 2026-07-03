# Incident Investigation (II)

**Route:** `/investigation`  
**Audience:** On-call engineers, engineering managers  
**Abbreviation:** II

> **Technical deep-dive:** Repo `backend/docs/incident-investigation-current.md`

---

## Purpose

When high-priority alerts land, II provides a mission-control layout to:

- Browse and filter **past and active incidents** by lifecycle status
- **Chat** with an assistant that traverses the Cognee knowledge graph
- Review **diagnostics**: probable root cause, confidence, emergency workaround
- See **recommended SMEs** and searchable **references** (Slack, Notion, postmortems)
- **Update incident status** as investigation progresses

---

## Workspace layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Incident history bar — status tabs + horizontal incident cards         │
├──────────────────┬──────────────────────┬───────────────────────────────┤
│  Left: Chat      │  Center: Diagnostics │  Right: Context & experts     │
│  SSE streaming   │  Confidence gauge    │  SME list + compatibility %   │
│  Suggestion chips│  Root cause          │  Reference search             │
│                  │  Workaround          │                               │
│                  │  Graph hops          │                               │
│                  │  Status dropdown     │                               │
└──────────────────┴──────────────────────┴───────────────────────────────┘
```

---

## Incident lifecycle

| Status | Meaning |
|--------|---------|
| **Open** | New or unassigned |
| **Investigating** | Active root-cause work |
| **Waiting for Input** | Blocked on external info |
| **Resolved** | Mitigation applied; monitoring |
| **Closed** | Fully closed |

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Route | `/investigation` (sidebar: Incident Investigation) |
| Integration gate | Jira connected and validated |
| Demo data | Five seeded incidents on tenant bootstrap (Payment Gateway, Auth Service, Notification Hub) |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/investigation/statuses` | Valid status strings |
| `GET` | `/api/investigation/incidents` | List; optional `?status=` filter |
| `PATCH` | `/api/investigation/incidents/{id}` | Update status |
| `POST` | `/api/investigation/chat/stream` | SSE chat → tokens + diagnostics |

All routes require authenticated tenant context.

---

## Chat & diagnostics flow

1. Parse **system scope** from user message (keyword match against known systems)
2. Extract optional **Jira ticket ID** (`PROJ-992` pattern)
3. Attempt **`tenant_graph_search()`** against tenant Cognee dataset (best-effort)
4. Stream narrative tokens over SSE (`type: token`)
5. Emit final **`type: diagnostics`** chunk

Diagnostics payload includes:

- Probable root cause narrative
- Confidence score
- Emergency workaround
- Graph hop trail
- SME recommendations (name, role, compatibility %)
- References (Slack, Notion, postmortems)

---

## Real vs simulated (current)

| Capability | Status |
|------------|--------|
| Incident list & status persistence | **Real** — PostgreSQL |
| Tenant-scoped queries | **Real** |
| Dashboard open-incident count sync | **Real** |
| Cognee search during chat | **Attempted** — not yet wired into diagnostics |
| Root cause, SMEs, references | **Simulated** — templates by system scope |
| SSE narrative | **Simulated** — tokenized mock with delay |
| Live Jira/Slack/Notion in II | **Not wired** — demo references |

---

## Dashboard coupling

- Open incident count on `/dashboard` = non-Resolved / non-Closed incidents
- Resolving/closing in II calls `notifyIncidentResolved()` → optimistic dashboard decrement

---

## KRA connection

**Incident Knowledge Debt** (KRA metric 3) closes the loop: repeat incidents without doc updates surface in KRA; II is where incidents are triaged and resolved.

---

## Related

- [KRA design](./02-kra.md) — incident knowledge debt metric
- [Integrations](./06-integrations-platform.md) — Jira gate
- [Runbook: troubleshooting](../runbooks/05-troubleshooting.md)
