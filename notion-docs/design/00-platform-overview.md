# Empulse — Platform Overview

**Audience:** Engineering managers, platform engineers, product  
**Status:** Living document — mirrors repo `cursor.md` and module design docs

---

## Executive summary

Empulse is an **engineering intelligence platform** for engineering managers. It unifies org knowledge, incident response, risk analytics, and offboarding into one cockpit — built on a live **Cognee** knowledge graph.

**Core question the platform answers:**

> If key people or systems fail tomorrow, what breaks — and can we prove why?

---

## Architecture

| Layer | Stack | Default port |
|-------|-------|--------------|
| Frontend | Next.js 15, React 19, Tailwind, Recharts, Lucide | `3000` |
| Backend | FastAPI, SQLAlchemy, Pydantic, Cognee | `8000` |
| Operational DB | PostgreSQL 16 | `5432` |
| LLM / embeddings | Ollama (`llama3.2`, `nomic-embed-text`) | `11434` |
| Graph / vectors | Cognee (Kuzu graph + LanceDB vectors; Neo4j optional) | local files |

```
┌─────────────┐     REST/SSE      ┌─────────────┐
│  Next.js UI │ ◄──────────────► │   FastAPI   │
└─────────────┘                   └──────┬──────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              PostgreSQL            Cognee graph         External APIs
           (tenant-scoped)      (per-tenant dataset)   GitHub/Jira/Notion/Slack
```

### Code layout

```
frontend/src/app/          App Router pages per module
frontend/src/components/   Feature components by module
frontend/src/lib/          api.ts, types.ts
backend/app/routes/        Thin HTTP routers
backend/app/services/      Business logic, Cognee, analytics
backend/app/schemas/       Pydantic models
backend/app/models/        SQLAlchemy tables
```

---

## Product modules

| Route | Name | Centricity | Primary question |
|-------|------|------------|------------------|
| `/dashboard` | Manager cockpit | Org | How is the team doing right now? |
| `/era` | Employee Risk Assessment | **Person** | Who is at continuity risk if they leave? |
| `/kra` | Knowledge Risk Assessment | **System** | Where is knowledge trapped? |
| `/investigation` | Incident Investigation | Incident | What caused this outage? |
| `/exit` | Employee Exit | Person → handover | What must transfer before they go? |
| `/settings` | Settings | Platform | Connect integrations, debug graph |
| `/onboarding` | Onboarding wizard | Tenant | Bootstrap org + connectors |

### Acronyms

| Acronym | Expansion |
|---------|-----------|
| ERA | Employee Risk Assessment |
| KRA | Knowledge Risk Assessment |
| II | Incident Investigation |
| EE | Employee Exit |
| SPOF | Single Point of Failure |
| DOA | Degree of Authorship (GitHub file ownership) |

---

## Data flow

```
Onboarding / integrations
        │
        ▼
Identity map (EmployeeIdentity) ──► quarantine if unmapped
        │
        ▼
Integration sync (GitHub, Jira, Notion, Slack)
        │
        ├──► PostgreSQL snapshots (telemetry, incidents, assignments)
        │
        └──► Cognee ingest ──► tenant-scoped knowledge graph
                    │
                    ├── ERA: person risk scores + evidence
                    ├── KRA: component SPOF, doc edges, blast radius
                    ├── II: graph search during investigation chat
                    └── Exit: handover markdown pre-fill from ERA
```

### Tenant isolation

- **PostgreSQL:** every row scoped by `tenant_id`
- **Cognee:** dataset name `empulse_tenant_{uuid-without-hyphens}`
- **API:** authenticated tenant context on all analytics routes

---

## Design principles (platform-wide)

| Principle | Rule |
|-----------|------|
| **Explainable risk** | Every score links to evidence artifacts |
| **No silent mis-attribution** | Unmapped external activity → quarantine queue |
| **Honest degradation** | Missing integration → partial badge, not fake zeros |
| **Deterministic numbers** | KPIs from SQL + graph edges; LLM for narrative only |
| **Cross-module links** | ERA ↔ KRA ↔ Exit ↔ II share the same graph |

---

## API surface (summary)

| Prefix | Key endpoints |
|--------|---------------|
| `/api/ingest` | `POST /org-chart` |
| `/api/analytics` | `GET /era`, `GET /kra`, `GET /kra/summary` |
| `/api/investigation` | incidents list, status update, chat stream |
| `/api/exit` | employees, handover markdown |
| `/api/dashboard` | aggregate metrics |
| `/api/integrations` | config, sync, telemetry |
| `/api/identity` | employee ↔ provider mappings |

---

## Related documents

- [ERA design](./01-era.md) → full spec in repo `design-docs/era/`
- [KRA design](./02-kra.md)
- [Incident Investigation](./03-incident-investigation.md)
- [Employee Exit](./04-employee-exit.md)
- [Runbook: local development](../runbooks/01-local-development.md)
