from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.role_evolution import (
    EmployeeUpdateRequest,
    EmployeeUpdateResponse,
    RoleHistoryRecord,
)
from app.services.org_chart_read import load_org_chart
from app.services.role_evolution import (
    list_active_roles,
    list_role_history,
    update_employee_with_role_evolution,
)
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/org", tags=["org"])


@router.get("/roles", response_model=list[str])
def get_active_roles(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[str]:
    return list_active_roles(db, tenant)


@router.get(
    "/employees/{employee_id}/role-history",
    response_model=list[RoleHistoryRecord],
)
def get_employee_role_history(
    employee_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> list[RoleHistoryRecord]:
    org = load_org_chart(db, tenant)
    if not any(employee.id == employee_id for employee in org.employees):
        raise HTTPException(status_code=404, detail="Employee not found.")
    return list_role_history(db, employee_id, tenant)


@router.patch(
    "/employees/{employee_id}",
    response_model=EmployeeUpdateResponse,
)
async def patch_employee(
    employee_id: str,
    payload: EmployeeUpdateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EmployeeUpdateResponse:
    org = load_org_chart(db, tenant)
    if not any(employee.id == employee_id for employee in org.employees):
        raise HTTPException(status_code=404, detail="Employee not found.")

    if payload.manager_id:
        employee_ids = {employee.id for employee in org.employees}
        if payload.manager_id not in employee_ids:
            raise HTTPException(status_code=422, detail="Unknown manager_id.")

    if payload.assignments is not None:
        component_ids = {component.id for component in org.components}
        for component_id in payload.assignments.component_ids:
            if component_id not in component_ids:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown component_id '{component_id}'.",
                )

    try:
        return await update_employee_with_role_evolution(
            db, employee_id, payload, tenant
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Employee update failed during Cognee sync: {exc}",
        ) from exc
