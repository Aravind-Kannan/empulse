"""Public health endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health/db")
def health_database():
    """
    Ping Postgres. Used on production landing page load to warm free-tier DB
    and surface cold-start connectivity issues to visitors.
    """
    ok, detail = check_database_connection()
    payload = {
        "postgres": "ok" if ok else "unavailable",
        "environment": get_settings().app_env,
    }
    if detail:
        payload["detail"] = detail
    if ok:
        return payload
    return JSONResponse(status_code=503, content=payload)
