from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.exit import DashboardMetrics, EmployeeOption, HandoverResponse
from app.services.dashboard import get_dashboard_metrics
from app.services.exit_handover import build_handover_markdown, list_exit_candidates
from app.tenancy import CurrentTenant

router = APIRouter(tags=["exit"])


@router.get("/api/exit/employees", response_model=list[EmployeeOption])
def get_exit_employees(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[EmployeeOption]:
    return list_exit_candidates(db, tenant)


@router.get("/api/exit/handover", response_model=HandoverResponse)
def get_handover(
    tenant: CurrentTenant,
    id: str = Query(..., description="Employee id"),
    prefill: str | None = Query(
        None,
        description="When set to 'era', enrich handover with ERA evidence sections",
    ),
    db: Session = Depends(get_db),
) -> HandoverResponse:
    try:
        return build_handover_markdown(
            db,
            id,
            tenant,
            prefill_era=prefill == "era",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> DashboardMetrics:
    return get_dashboard_metrics(db, tenant)
