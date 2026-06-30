# Empulse — Cursor Project Guide

Engineering intelligence platform for engineering managers. Unifies org knowledge, incident response, risk analytics, and offboarding into one cockpit — built on a live **Cognee** knowledge graph.

**Tagline:** Engineering Intelligence Powered by Cognee

---

## Architecture

Dual-stack monorepo:

| Layer | Stack | Port |
|-------|-------|------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Recharts, Lucide | `3000` |
| Backend | FastAPI, SQLAlchemy, Cognee, Pydantic | `8000` |
| Operational DB | PostgreSQL 16 (Docker) | `5432` |
| LLM / Embeddings | Ollama (`llama3.2`, `nomic-embed-text`) | `11434` |
| Graph / Vector | Cognee (Kuzu graph + LanceDB vectors) | local files |

```
frontend/          Next.js App Router UI
backend/
  app/
    routes/        FastAPI routers (thin — delegate to services)
    services/      Business logic, Cognee ingestion, analytics
    schemas/       Pydantic request/response models
    models/        SQLAlchemy operational tables
  scripts/         CLI utilities (e.g. Notion simulation)
prompts/           Original build prompts (reference only)
```

---

## Product Modules

| Route | Module | Purpose |
|-------|--------|---------|
| `/` | Landing / Auth | Login, sign-up → onboarding |
| `/onboarding` | Onboarding wizard | Org chart setup, integration config |
| `/dashboard` | Manager cockpit | Aggregate metrics, digest settings |
| `/era` | Employee Risk Assessment | Burnout, bottlenecks, risk scores |
| `/kra` | Knowledge Risk Assessment | Dependency graph, SPOF detection |
| `/investigation` | Incident Investigation | 3-panel root-cause workspace |
| `/exit` | Employee Exit | Handover pack generation |
| `/settings` | Settings hub | Integrations, graph debugger |

### Key acronyms
- **ERA** — Employee Risk Assessment
- **KRA** — Knowledge Risk Assessment
- **II** — Incident Investigation
- **EE** — Employee Exit
- **SPOF** — Single Point of Failure

---

## Local Development

### Prerequisites
- Docker (PostgreSQL)
- Python 3.11+ with venv
- Node.js 20+
- Ollama running locally with `llama3.2` and `nomic-embed-text`

### Start services

```bash
# PostgreSQL
docker compose up -d

# Backend (from backend/)
cp .env.example .env   # first time only
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/)
npm install
npm run dev
```

### Environment
Copy `backend/.env.example` → `backend/.env`. Key variables:

- `DATABASE_URL` — defaults to `postgresql+psycopg2://postgres:postgres@localhost:5432/empulse`
- `COGNEE_DATASET_NAME` — defaults to `empulse_org_chart`
- Ollama LLM/embedding settings (see `.env.example`)

Frontend API base: `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

---

## Backend Conventions

### Router → Service pattern
- **Routes** (`app/routes/`) — HTTP handling, validation, status codes only.
- **Services** (`app/services/`) — All business logic, Cognee calls, DB queries.
- **Schemas** (`app/schemas/`) — Pydantic models; mirror frontend types in `frontend/src/lib/types.ts`.

### Cognee integration
- Initialized in `app/config.py` via `setup_cognee()` on app startup.
- Ingestion helper: `run_cognee_add_and_cognify(content, dataset_name=...)`.
- Runtime data lives in `backend/.data_storage/`, `.cognee_system/`, `.cognee_cache/` (gitignored).
- Default dataset: `empulse_org_chart`; simulation uses `empulse_notion_simulation`.

### External integrations
Mock/sync pipeline in `app/services/integration_sync.py`:
- **GitHub** — commits, PRs, file paths → `contributedTo` / `modifies` graph edges
- **Jira** — tickets, priorities, assignees → `blocksComponent` / `assignedTo` edges
- Sync entry point: `process_external_app_sync(source)` and `process_global_sync()`
- Telemetry updates cascade to ERA/KRA via `integration_telemetry.py`

### API routes

| Prefix | Endpoints |
|--------|-----------|
| `/api/ingest` | `POST /org-chart` |
| `/api/analytics` | `GET /era`, `GET /kra`, `POST /kra/assign-backup` |
| `/api/investigation` | `GET /incidents`, `PATCH /incidents/{id}`, `POST /chat/stream` |
| `/api/exit` | `GET /employees`, `GET /handover` |
| `/api/dashboard` | `GET /metrics` (via exit router) |
| `/api/integrations` | GitHub/Jira config, `POST /sync`, `POST /sync/{source}`, telemetry |
| `/api/test` | `POST /run-simulation`, `POST /run-simulation/stream` |

---

## Frontend Conventions

### Structure
- **Pages** — `frontend/src/app/**/page.tsx` (thin wrappers)
- **Components** — `frontend/src/components/{module}/` grouped by feature
- **API client** — `frontend/src/lib/api.ts` (all fetch calls)
- **Types** — `frontend/src/lib/types.ts`
- **Context** — React Context providers in `frontend/src/context/`

### State management
Global providers (see `components/Providers.tsx`):
- `AuthContext` — mock auth session (`empulse-auth-session` in localStorage)
- `WorkspaceContext` — digest settings, cross-module state
- `IntegrationsContext` — integration configs (`empulse-integrations-config`)
- `OnboardingContext` — wizard step state

### UI / styling
- Dark theme: Slate/Zinc palette (`bg-slate-950`, `text-zinc-100`, `border-zinc-800`)
- `"use client"` on interactive components; pages can be server or client
- `AppShell` hides sidebar on `/` and `/onboarding`
- Icons from `lucide-react`; charts from `recharts`
- KRA graph uses custom SVG/canvas (not React Flow)

### Auth flow
- `/` — landing with Login / Sign Up modals
- Sign Up → `/onboarding` (3-step wizard)
- Login → `/dashboard`
- `AuthGuard` protects authenticated routes

---

## Coding Guidelines for Agents

1. **Minimize scope** — Match existing patterns; don't refactor unrelated code.
2. **Keep routes thin** — Put logic in services, types in schemas.
3. **Mirror types** — When adding API fields, update both Pydantic schemas and `frontend/src/lib/types.ts`.
4. **Use existing API client** — Add new fetch helpers to `lib/api.ts`, not inline in components.
5. **Respect the dark theme** — Use zinc/slate Tailwind classes consistent with existing UI.
6. **Cognee is async** — Use `await cognee.add()` / `await cognee.cognify()` in async service functions.
7. **Don't commit secrets** — `.env` is gitignored; update `.env.example` for new vars.
8. **Don't commit Cognee runtime dirs** — `.data_storage/`, `.cognee_system/`, `.cognee_cache/`.
9. **Integration sync affects ERA/KRA** — Changes to ingestion should update telemetry hooks.
10. **Mock data is intentional** — GitHub/Jira feeds and investigation chat use simulated responses for the hackathon demo.

---

## Key Files

| File | Role |
|------|------|
| `backend/app/main.py` | FastAPI app, router registration, lifespan |
| `backend/app/config.py` | Settings, Cognee setup, ingest helper |
| `backend/app/database.py` | SQLAlchemy engine, session, init |
| `backend/app/services/cognee_ingest.py` | Org chart → Cognee graph |
| `backend/app/services/era_analytics.py` | ERA risk score computation |
| `backend/app/services/kra_analytics.py` | KRA graph + SPOF detection |
| `backend/app/services/investigation.py` | Incident chat streaming |
| `backend/app/services/notion_simulation.py` | Notion → Cognee E2E pipeline |
| `frontend/src/lib/api.ts` | All backend API calls |
| `frontend/src/components/Sidebar.tsx` | Main navigation |
| `docker-compose.yml` | PostgreSQL (`empulse` DB) |

---

## Scripts

```bash
# Notion → Cognee simulation (from backend/)
python scripts/test_notion_cognee.py \
  --notion-token "$NOTION_INTEGRATION_TOKEN" \
  --notion-database-id "$NOTION_DATABASE_ID"
```

Graph debugger UI: `/settings/graph-debugger` — streams simulation and renders the resulting graph.

---

## Prompts Directory

`prompts/01_*.md` through `prompts/12_*.md` document the original incremental build plan. Use as reference for intended behavior; the live codebase may have diverged.
