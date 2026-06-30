from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.exit import DashboardMetrics, EmployeeOption, HandoverResponse
from app.services.dashboard import get_dashboard_metrics
from app.services.exit_handover import build_handover_markdown, list_exit_candidates

router = APIRouter(tags=["exit"])


@router.get("/api/exit/employees", response_model=list[EmployeeOption])
def get_exit_employees(db: Session = Depends(get_db)) -> list[EmployeeOption]:
    return list_exit_candidates(db)


@router.get("/api/exit/handover", response_model=HandoverResponse)
def get_handover(
    id: str = Query(..., description="Employee id"),
    db: Session = Depends(get_db),
) -> HandoverResponse:
    try:
        return build_handover_markdown(db, id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(db: Session = Depends(get_db)) -> DashboardMetrics:
    return get_dashboard_metrics(db)
