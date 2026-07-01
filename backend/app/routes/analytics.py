from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.era import EraAnalyticsResponse, EraEmployeeDetailResponse
from app.schemas.kra import (
    KraAnalyticsResponse,
    KraBackupAssignmentRequest,
    KraBackupAssignmentResponse,
)
from app.services.era_analytics import get_era_employee_detail, get_era_metrics
from app.services.kra_analytics import (
    assign_backup_engineer,
    get_kra_graph,
    is_component_spof_resolved,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/era", response_model=EraAnalyticsResponse)
def era_analytics(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraAnalyticsResponse:
    return get_era_metrics(db, tenant)


@router.get("/era/{employee_id}", response_model=EraEmployeeDetailResponse)
def era_employee_detail(
    employee_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EraEmployeeDetailResponse:
    detail = get_era_employee_detail(
        db,
        tenant,
        employee_id,
        limit=limit,
        offset=offset,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")
    return detail


@router.get("/kra", response_model=KraAnalyticsResponse)
def kra_analytics(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> KraAnalyticsResponse:
    return get_kra_graph(db, tenant)


@router.post("/kra/assign-backup", response_model=KraBackupAssignmentResponse)
def kra_assign_backup(
    payload: KraBackupAssignmentRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> KraBackupAssignmentResponse:
    try:
        assign_backup_engineer(
            db,
            tenant=tenant,
            component_id=payload.component_id,
            employee_id=payload.employee_id,
            codebase_share_pct=payload.codebase_share_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return KraBackupAssignmentResponse(
        component_id=payload.component_id,
        employee_id=payload.employee_id,
        codebase_share_pct=payload.codebase_share_pct,
        is_spof_resolved=is_component_spof_resolved(db, tenant, payload.component_id),
    )
