# Empulse — Notion Documentation Pack

Engineering intelligence platform documentation formatted for import into Notion.

**Tagline:** Engineering Intelligence Powered by Cognee

---

## How to use in Notion

1. Create a top-level page: **Empulse**
2. Import each markdown file below (Notion → **Import** → **Markdown & CSV**), or paste sections into child pages
3. Keep **Design** and **Runbooks** as separate top-level sections under Empulse
4. ERA deep-dive lives in the repo at `design-docs/era/` — link or mirror as needed; this pack summarizes and cross-links

---

## Design documents

| Doc | Audience | Summary |
|-----|----------|---------|
| [Platform overview](./design/00-platform-overview.md) | All | Architecture, modules, data flow, acronyms |
| [ERA — Employee Risk Assessment](./design/01-era.md) | EMs, HR partners | Person-centric continuity risk; links to full ERA spec |
| [KRA — Knowledge Risk Assessment](./design/02-kra.md) | EMs, staff engineers | Component-centric SPOF, doc coverage, blast radius |
| [Incident Investigation](./design/03-incident-investigation.md) | On-call, EMs | II workspace, lifecycle, diagnostics |
| [Employee Exit](./design/04-employee-exit.md) | EMs, HR | Handover pack generation, ERA bridge |
| [Manager Dashboard](./design/05-dashboard.md) | EMs | Cockpit metrics, digest, setup checklist |
| [Integrations & platform](./design/06-integrations-platform.md) | Platform, DevOps | GitHub, Jira, Notion, Slack, identity, sync |
| [Onboarding & auth](./design/07-onboarding-auth.md) | New tenants | Wizard, org chart ingest, auth flow |

---

## Runbooks

| Runbook | When to use |
|---------|-------------|
| [Local development](./runbooks/01-local-development.md) | First-time setup, daily dev |
| [Integration sync](./runbooks/02-integration-sync.md) | Connectors, manual sync, telemetry |
| [Cognee & graph operations](./runbooks/03-cognee-graph-operations.md) | Ingest, datasets, graph debugger |
| [Tenant & Neo4j inspection](./runbooks/04-tenant-neo4j-inspection.md) | Debug tenant isolation, Cypher queries |
| [Troubleshooting](./runbooks/05-troubleshooting.md) | Common failures, logs, recovery |
| [ERA review cadence](./runbooks/06-era-review-cadence.md) | Monthly manager risk review ritual |

---

## Repo references (not duplicated here)

| Path | Contents |
|------|----------|
| `design-docs/era/` | Full ERA design + 18 implementation steps |
| `prompts/kra/` | KRA metric implementation prompts |
| `backend/docs/incident-investigation-current.md` | II technical deep-dive |
| `backend/docs/neo4j-tenant-queries.md` | Neo4j Cypher reference |
| `cursor.md` | Agent/developer project guide |
| `docs/features/` | Feature components + mapped source paths for GitHub attribution |

---

## Module quick map

| Route | Module | Acronym |
|-------|--------|---------|
| `/dashboard` | Manager cockpit | — |
| `/era` | Employee Risk Assessment | ERA |
| `/kra` | Knowledge Risk Assessment | KRA |
| `/investigation` | Incident Investigation | II |
| `/exit` | Employee Exit | EE |
| `/settings` | Integrations, graph debugger | — |
| `/onboarding` | Tenant setup wizard | — |
