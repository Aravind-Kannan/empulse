from fastapi import APIRouter

from app.schemas.tenant import TenantSummary
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
