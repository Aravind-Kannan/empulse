from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.identity import (
    EmployeeIdentityRecord,
    IdentityMappingsUpdateRequest,
    IdentityReconciliationResponse,
    IdentitySyncRequest,
    IdentitySyncResponse,
    ProviderIdentitySyncResult,
    ProviderMember,
    ProviderMembersBundleResponse,
    UnmappedActivityListResponse,
)
from app.services.identity_mapping import (
    PROVIDERS,
    get_provider_members,
    get_reconciliation,
    list_identity_mappings,
    load_provider_members_bundle,
    save_identity_mappings,
)
from app.services.identity_sync import refresh_identity_mappings
from app.services.provider_members import build_fetch_users_request_for_sources
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
    include_live_members: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> IdentityReconciliationResponse:
    providers = connected if connected else list(PROVIDERS)
    return get_reconciliation(
        db,
        tenant,
        connected_providers=providers,
        include_live_members=include_live_members,
    )


@router.get("/provider-members", response_model=ProviderMembersBundleResponse)
def read_provider_members_bundle(
    tenant: CurrentTenant,
    connected: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
) -> ProviderMembersBundleResponse:
    providers = connected if connected else list(PROVIDERS)
    members, warnings = load_provider_members_bundle(db, tenant.id, providers)
    return ProviderMembersBundleResponse(
        provider_members=members,
        provider_warnings=warnings,
    )


@router.put("/mappings", response_model=list[EmployeeIdentityRecord])
def update_identity_mappings(
    payload: IdentityMappingsUpdateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[EmployeeIdentityRecord]:
    return save_identity_mappings(db, tenant, payload.mappings)


@router.post("/sync", response_model=IdentitySyncResponse)
async def sync_identity_mappings(
    payload: IdentitySyncRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> IdentitySyncResponse:
    """
    Pull provider member directories and auto-map identities by email.

    Use after onboarding when integrations change or unmapped activity grows.
    """
    providers = payload.providers or list(PROVIDERS)
    credentials = None
    if payload.import_roster:
        credentials = build_fetch_users_request_for_sources(db, tenant.id, providers)
        if payload.company:
            credentials = credentials.model_copy(update={"company": payload.company})
        elif tenant.company_name:
            credentials = credentials.model_copy(update={"company": tenant.company_name})

    try:
        result = await refresh_identity_mappings(
            db,
            tenant,
            providers=providers,
            import_roster=payload.import_roster,
            credentials=credentials,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Identity sync failed: {exc}",
        ) from exc

    provider_rows = [
        ProviderIdentitySyncResult(**row) for row in result["providers"]
    ]
    return IdentitySyncResponse(
        providers=provider_rows,
        total_mappings_created=int(result["total_mappings_created"]),
        roster=result.get("roster"),
    )


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
