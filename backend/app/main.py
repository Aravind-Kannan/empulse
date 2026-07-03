from app.ssl import configure_ssl

configure_ssl()

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings, setup_cognee
from app.database import init_db
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.test_simulation import router as test_simulation_router
from app.routes.internal import router as internal_router
from app.routes.integrations import router as integrations_router
from app.routes.ingest import router as ingest_router
from app.routes.exit import router as exit_router
from app.routes.identity import router as identity_router
from app.routes.org_bulk import router as org_bulk_router
from app.routes.org_employees import router as org_employees_router
from app.routes.org_components import router as org_components_router
from app.routes.investigation import router as investigation_router
from app.routes.jira import router as jira_router
from app.routes.tenants import router as tenants_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_cognee()
    init_db()

    from app.services.integration_sync_jobs import recover_orphaned_sync_jobs

    recovered = recover_orphaned_sync_jobs()
    if recovered:
        logger.warning(
            "Marked %d orphaned integration sync job(s) failed after restart",
            recovered,
        )

    from cognee.run_migrations import run_relational_migrations

    await run_relational_migrations()

    from app.database import SessionLocal
    from app.services.tenant_bootstrap import bootstrap_tenancy
    from app.services.tenant_cognee import ensure_tenant_cognee_dataset

    db = SessionLocal()
    try:
        tenant = bootstrap_tenancy(db)
        await ensure_tenant_cognee_dataset(tenant.id)
    finally:
        db.close()

    logger.info(
        "API ready. Heavy sync/ingest jobs are serialized (one at a time). "
        "Avoid uvicorn --reload during long syncs."
    )

    yield


app = FastAPI(
    title="Empulse API",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(ingest_router)
app.include_router(integrations_router)
app.include_router(test_simulation_router)
app.include_router(analytics_router)
app.include_router(investigation_router)
app.include_router(identity_router)
app.include_router(org_bulk_router)
app.include_router(org_employees_router)
app.include_router(org_components_router)
app.include_router(exit_router)
app.include_router(jira_router)
app.include_router(tenants_router)
app.include_router(internal_router)


@app.get("/")
def read_root():
    return {"status": "healthy", "engine": "Cognee Knowledge Graph"}
