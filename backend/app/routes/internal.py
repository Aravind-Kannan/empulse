"""Internal debugging routes (not for production exposure without protection)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import get_settings
from app.schemas.tenant_storage import TenantCogneeStorageAccess
from app.services.tenant_storage_access import get_tenant_cognee_storage_access
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/internal", tags=["internal"])


def verify_internal_debug_key(
    x_internal_debug_key: str | None = Header(default=None, alias="X-Internal-Debug-Key"),
) -> None:
    settings = get_settings()
    if not settings.internal_debug_key:
        return
    if x_internal_debug_key != settings.internal_debug_key:
        raise HTTPException(status_code=403, detail="Invalid internal debug key.")


@router.get(
    "/tenants/current/neo4j-access",
    response_model=TenantCogneeStorageAccess,
    dependencies=[Depends(verify_internal_debug_key)],
)
async def get_current_tenant_neo4j_access(
    tenant: CurrentTenant,
) -> TenantCogneeStorageAccess:
    """Neo4j Browser connection details for the active tenant."""
    return await get_tenant_cognee_storage_access(tenant.id)


@router.get(
    "/tenants/{tenant_id}/neo4j-access",
    response_model=TenantCogneeStorageAccess,
    dependencies=[Depends(verify_internal_debug_key)],
)
async def get_tenant_neo4j_access(tenant_id: uuid.UUID) -> TenantCogneeStorageAccess:
    """Neo4j Browser connection details for a specific tenant."""
    return await get_tenant_cognee_storage_access(tenant_id)
