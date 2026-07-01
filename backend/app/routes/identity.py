from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.identity import (
    EmployeeIdentityRecord,
    IdentityMappingsUpdateRequest,
    IdentityReconciliationResponse,
    ProviderMember,
    UnmappedActivityListResponse,
)
from app.services.identity_mapping import (
    PROVIDERS,
    get_provider_members,
    get_reconciliation,
    list_identity_mappings,
    save_identity_mappings,
)
from app.services.unmapped_activity import (
    get_total_unmapped_count,
    get_unmapped_counts_by_provider,
    list_unmapped_activities,
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
def read_provider_members(
    provider: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[ProviderMember]:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'.")
    try:
        return get_provider_members(provider, db, tenant.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/unmapped", response_model=UnmappedActivityListResponse)
def read_unmapped_activities(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    provider: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> UnmappedActivityListResponse:
    if provider and provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'.")
    return UnmappedActivityListResponse(
        items=list_unmapped_activities(db, tenant.id, provider=provider, limit=limit),
        total_unmapped_count=get_total_unmapped_count(db, tenant.id),
        unmapped_by_provider=get_unmapped_counts_by_provider(db, tenant.id),
    )
