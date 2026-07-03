# Runbook: Troubleshooting

**Owner:** All engineers  
**When:** Something breaks in dev or staging

---

## Quick diagnostics

| Check | Command / URL |
|-------|---------------|
| Backend up | http://localhost:8000/docs |
| Frontend up | http://localhost:3000 |
| PostgreSQL | `docker compose ps` |
| Ollama | `curl http://localhost:11434/api/tags` |
| Backend logs | uvicorn terminal output |

---

## Symptom → fix

### API returns 401 / no tenant

| Cause | Fix |
|-------|-----|
| Not logged in | Sign up or login via `/` |
| Missing tenant header | Ensure `X-Tenant-ID` or auth cookie set |
| Session cleared | Re-login; check `empulse-auth-session` in localStorage |

### ERA/KRA empty or all zeros

| Cause | Fix |
|-------|-----|
| No org chart | Complete onboarding or `POST /api/ingest/org-chart` |
| No sync run | [Integration sync](./02-integration-sync.md) |
| Identity unmapped | Reconcile identity mappings |
| Demo vs live mismatch | Check tenant `demo_mode` flag |

### Cognee / graph errors

| Cause | Fix |
|-------|-----|
| Ollama not running | Start Ollama; pull required models |
| Corrupt local graph | [Reset Cognee dirs](./03-cognee-graph-operations.md) |
| Wrong dataset | Verify tenant UUID → dataset name |

### Integration sync fails

| Cause | Fix |
|-------|-----|
| Expired token | Rotate in Settings |
| Rate limit | Retry single-source sync |
| Wrong scope | Verify repo/project/database IDs in config |

### II chat streams but diagnostics empty

Expected in current build — diagnostics are template-driven per system scope. Cognee search is best-effort and not yet wired into diagnostics payload.

### Frontend can't reach backend

| Cause | Fix |
|-------|-----|
| Wrong API URL | Set `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| CORS | Backend CORS must include `http://localhost:3000` |
| Backend down | Restart uvicorn |

### Database connection refused

```bash
docker compose up -d
# Verify DATABASE_URL matches docker-compose postgres settings
```

### Migrations / schema drift

```bash
cd backend
# Re-init if dev DB is disposable
python -c "from app.database import init_db; init_db()"
```

---

## Log locations

| Component | Where |
|-----------|-------|
| FastAPI | uvicorn stdout |
| Cognee | backend logs + `.cognee_system/` |
| PostgreSQL | `docker compose logs postgres` |
| Neo4j | `docker compose logs neo4j` |

---

## Escalation checklist

Before filing an issue, capture:

1. Tenant UUID
2. Steps to reproduce
3. Relevant API response (redact tokens)
4. Whether integrations are connected
5. `demo_mode` on/off
6. Backend log snippet around error time

---

## Related

- [Local development](./01-local-development.md)
- [Integration sync](./02-integration-sync.md)
- [Cognee operations](./03-cognee-graph-operations.md)
