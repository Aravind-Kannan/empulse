from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import setup_cognee
from app.database import init_db
from app.routes.analytics import router as analytics_router
from app.routes.test_simulation import router as test_simulation_router
from app.routes.integrations import router as integrations_router
from app.routes.ingest import router as ingest_router
from app.routes.exit import router as exit_router
from app.routes.investigation import router as investigation_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_cognee()
    init_db()
    yield


app = FastAPI(
    title="Empulse API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(integrations_router)
app.include_router(test_simulation_router)
app.include_router(analytics_router)
app.include_router(investigation_router)
app.include_router(exit_router)


@app.get("/")
def read_root():
    return {"status": "healthy", "engine": "Cognee Knowledge Graph"}
