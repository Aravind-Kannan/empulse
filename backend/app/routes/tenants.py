from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.tenant import TenantSummary, WorkspaceWipeResponse
from app.services.tenant_workspace_wipe import wipe_tenant_operational_data
from app.tenancy import CurrentTenant, tenant_dataset_name

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantSummary)
def get_current_tenant_info(tenant: CurrentTenant) -> TenantSummary:
    return TenantSummary.model_validate(tenant)


@router.get("/current/dataset")
def get_current_tenant_dataset(tenant: CurrentTenant) -> dict[str, str]:
    return {
        "tenant_id": str(tenant.id),
        "dataset_name": tenant_dataset_name(tenant.id),
    }


@router.post("/wipe-operational-data", response_model=WorkspaceWipeResponse)
def wipe_operational_data(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> WorkspaceWipeResponse:
    """Delete employees, components, incidents, and all derived analytics for this tenant."""
    result = wipe_tenant_operational_data(db, tenant.id)
    return WorkspaceWipeResponse(**result)
