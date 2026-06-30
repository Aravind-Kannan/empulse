from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.org import OrgChartIngestRequest, OrgChartIngestResponse
from app.services.cognee_ingest import ingest_org_chart_to_cognee, persist_org_chart

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/org-chart", response_model=OrgChartIngestResponse)
async def ingest_org_chart(
    payload: OrgChartIngestRequest,
    db: Session = Depends(get_db),
) -> OrgChartIngestResponse:
    employee_ids = {employee.id for employee in payload.employees}
    if len(employee_ids) != len(payload.employees):
        raise HTTPException(status_code=422, detail="Duplicate employee ids detected.")

    for employee in payload.employees:
        if employee.manager_id and employee.manager_id not in employee_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown manager_id '{employee.manager_id}' for employee '{employee.id}'.",
            )

    component_ids = {component.id for component in payload.components}
    for assignment in payload.assignments:
        if assignment.employee_id not in employee_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown employee_id '{assignment.employee_id}' in assignment.",
            )
        if assignment.component_id not in component_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown component_id '{assignment.component_id}' in assignment.",
            )

    try:
        persist_org_chart(db, payload)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to persist org chart to PostgreSQL: {exc}",
        ) from exc

    try:
        cognee_result = await ingest_org_chart_to_cognee(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"PostgreSQL write succeeded but Cognee ingestion failed: {exc}",
        ) from exc

    return OrgChartIngestResponse(
        company=payload.company,
        employees_persisted=len(payload.employees),
        components_persisted=len(payload.components),
        assignments_persisted=len(payload.assignments),
        cognee_dataset=str(cognee_result["cognee_dataset"]),
        graph_nodes_created=int(cognee_result["graph_nodes_created"]),
        graph_edges_created=int(cognee_result["graph_edges_created"]),
    )
