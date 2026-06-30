from app.ssl import configure_ssl

configure_ssl()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings, setup_cognee
from app.database import init_db
from app.routes.analytics import router as analytics_router
from app.routes.auth import router as auth_router
from app.routes.test_simulation import router as test_simulation_router
from app.routes.integrations import router as integrations_router
from app.routes.ingest import router as ingest_router
from app.routes.exit import router as exit_router
from app.routes.identity import router as identity_router
from app.routes.org_bulk import router as org_bulk_router
from app.routes.org_employees import router as org_employees_router
from app.routes.investigation import router as investigation_router
from app.routes.tenants import router as tenants_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_cognee()
    init_db()
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
app.include_router(exit_router)
app.include_router(tenants_router)


@app.get("/")
def read_root():
    return {"status": "healthy", "engine": "Cognee Knowledge Graph"}
