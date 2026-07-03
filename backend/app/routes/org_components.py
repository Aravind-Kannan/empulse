from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.component_management import (
    ComponentDeleteResponse,
    ComponentUpdateRequest,
    ComponentUpdateResponse,
)
from app.services.component_management import (
    consolidate_duplicate_components,
    delete_component_with_cognee_sync,
    update_component_with_cognee_sync,
)
from app.services.org_chart_read import load_org_chart
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/org", tags=["org"])


@router.post("/components/consolidate")
def consolidate_components(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    removed = consolidate_duplicate_components(db, tenant.id)
    return {"removed": removed}


@router.patch(
    "/components/{component_id}",
    response_model=ComponentUpdateResponse,
)
async def patch_component(
    component_id: str,
    payload: ComponentUpdateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> ComponentUpdateResponse:
    org = load_org_chart(db, tenant)
    if not any(component.id == component_id for component in org.components):
        raise HTTPException(status_code=404, detail="Component not found.")

    if not any(
        value is not None
        for value in (
            payload.name,
            payload.tags,
            payload.criticality,
            payload.description,
        )
    ):
        raise HTTPException(status_code=422, detail="No fields to update.")

    try:
        result = await update_component_with_cognee_sync(
            db,
            component_id,
            tenant=tenant,
            name=payload.name,
            tags=payload.tags,
            criticality=payload.criticality,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Component update failed during Cognee sync: {exc}",
        ) from exc

    return ComponentUpdateResponse(**result)


@router.delete(
    "/components/{component_id}",
    response_model=ComponentDeleteResponse,
)
async def delete_component(
    component_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> ComponentDeleteResponse:
    org = load_org_chart(db, tenant)
    if not any(component.id == component_id for component in org.components):
        raise HTTPException(status_code=404, detail="Component not found.")

    try:
        result = await delete_component_with_cognee_sync(
            db,
            component_id,
            tenant=tenant,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Component delete failed during Cognee sync: {exc}",
        ) from exc

    return ComponentDeleteResponse(**result)
