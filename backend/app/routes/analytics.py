from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.era import EraAnalyticsResponse
from app.schemas.kra import (
    KraAnalyticsResponse,
    KraBackupAssignmentRequest,
    KraBackupAssignmentResponse,
)
from app.services.era_analytics import get_era_metrics
from app.services.kra_analytics import (
    assign_backup_engineer,
    get_kra_graph,
    is_component_spof_resolved,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/era", response_model=EraAnalyticsResponse)
def era_analytics(db: Session = Depends(get_db)) -> EraAnalyticsResponse:
    return get_era_metrics(db)


@router.get("/kra", response_model=KraAnalyticsResponse)
def kra_analytics(db: Session = Depends(get_db)) -> KraAnalyticsResponse:
    return get_kra_graph(db)


@router.post("/kra/assign-backup", response_model=KraBackupAssignmentResponse)
def kra_assign_backup(
    payload: KraBackupAssignmentRequest,
    db: Session = Depends(get_db),
) -> KraBackupAssignmentResponse:
    try:
        assign_backup_engineer(
            db,
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
        is_spof_resolved=is_component_spof_resolved(db, payload.component_id),
    )
