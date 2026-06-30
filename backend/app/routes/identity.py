from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.identity import (
    EmployeeIdentityRecord,
    IdentityMappingsUpdateRequest,
    IdentityReconciliationResponse,
    ProviderMember,
)
from app.services.identity_mapping import (
    PROVIDERS,
    get_provider_members,
    get_reconciliation,
    list_identity_mappings,
    save_identity_mappings,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/identity", tags=["identity"])


@router.get("/mappings", response_model=list[EmployeeIdentityRecord])
def read_identity_mappings(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[EmployeeIdentityRecord]:
    return list_identity_mappings(db, tenant)


@router.get("/providers/{provider}/members", response_model=list[ProviderMember])
def read_provider_members(provider: str) -> list[ProviderMember]:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'.")
    return get_provider_members(provider)


@router.get("/reconciliation", response_model=IdentityReconciliationResponse)
def read_reconciliation(
    tenant: CurrentTenant,
    connected: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> IdentityReconciliationResponse:
    providers = connected if connected else list(PROVIDERS)
    return get_reconciliation(db, tenant, connected_providers=providers)


@router.put("/mappings", response_model=list[EmployeeIdentityRecord])
def update_identity_mappings(
    payload: IdentityMappingsUpdateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[EmployeeIdentityRecord]:
    return save_identity_mappings(db, tenant, payload.mappings)
