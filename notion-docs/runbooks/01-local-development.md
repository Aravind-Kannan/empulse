# Runbook: Local Development

**Owner:** Platform / all engineers  
**Last updated:** 2026-07

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker | PostgreSQL (+ optional Neo4j) |
| Python | 3.11+ |
| Node.js | 20+ |
| Ollama | Running with `llama3.2` + `nomic-embed-text` |

---

## First-time setup

### 1. Clone and configure

```bash
git clone <repo-url> empulse && cd empulse
cp backend/.env.example backend/.env
# Edit backend/.env — DATABASE_URL, Ollama, optional integration tokens
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

Default DB: `postgresql+psycopg2://postgres:postgres@localhost:5432/empulse`

### 3. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify: http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Verify: http://localhost:3000

### 5. Ollama models

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

Cognee uses these for cognify and graph completion.

---

## Daily workflow

```bash
# Terminal 1 — DB (if not running)
docker compose up -d

# Terminal 2 — backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — frontend
cd frontend && npm run dev
```

---

## Optional: Neo4j for graph inspection

```bash
docker compose up -d neo4j
```

Browser: http://localhost:7474  
Default creds: `neo4j` / `pleaseletmein` (see `.env`)

See [tenant Neo4j runbook](./04-tenant-neo4j-inspection.md).

---

## Key environment variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | localhost PostgreSQL | Required |
| `COGNEE_DATASET_NAME` | `empulse_org_chart` | Overridden per tenant |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → backend |

---

## Cognee runtime dirs (gitignored)

Do not commit:

- `backend/.data_storage/`
- `backend/.cognee_system/`
- `backend/.cognee_cache/`

Reset graph state: delete these dirs + re-ingest org chart.

---

## Smoke test

1. Sign up → complete onboarding wizard
2. `POST /api/ingest/org-chart` (via UI or curl)
3. Open `/era`, `/kra`, `/dashboard` — metrics should load
4. Settings → graph debugger — run simulation

---

## Related

- Repo `cursor.md` — agent developer guide
- [Integration sync](./02-integration-sync.md)
- [Troubleshooting](./05-troubleshooting.md)
