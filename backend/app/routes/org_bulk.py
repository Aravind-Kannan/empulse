from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.org import OrgChartIngestResponse
from app.schemas.org_bulk import BulkUploadRequest, BulkUploadResponse
from app.services.cognee_ingest import ingest_org_chart_to_cognee, persist_org_chart
from app.services.org_bulk import build_bulk_reindex_narrative, merge_bulk_org
from app.services.org_chart_read import load_org_chart
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/org", tags=["org"])


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_org(
    payload: BulkUploadRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> BulkUploadResponse:
    current_org = payload.current_org
    if current_org is None:
        current_org = load_org_chart(db, tenant)

    merged_org, errors, diff = merge_bulk_org(
        payload.company,
        payload.rows,
        current_org,
    )

    if errors or merged_org is None:
        return BulkUploadResponse(valid=False, errors=errors, diff=diff)

    if payload.dry_run:
        return BulkUploadResponse(
            valid=True,
            diff=diff,
            merged_org=merged_org,
        )

    try:
        scoped_payload = persist_org_chart(db, merged_org, tenant.id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=f"Failed to persist bulk org chart: {exc}",
        ) from exc

    try:
        cognee_result = await ingest_org_chart_to_cognee(
            scoped_payload,
            tenant_id=tenant.id,
            custom_prompt=(
                "Bulk re-index enterprise organizational structure. "
                "Replace prior reporting linkages and team metadata with this authoritative directory."
            ),
            supplemental_narrative=build_bulk_reindex_narrative(merged_org),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Bulk Cognee sync failed: {exc}",
        ) from exc

    return BulkUploadResponse(
        valid=True,
        diff=diff,
        merged_org=merged_org,
        sync_result=OrgChartIngestResponse(
            company=merged_org.company,
            employees_persisted=len(merged_org.employees),
            components_persisted=len(merged_org.components),
            assignments_persisted=len(merged_org.assignments),
            cognee_dataset=str(cognee_result["cognee_dataset"]),
            graph_nodes_created=int(cognee_result["graph_nodes_created"]),
            graph_edges_created=int(cognee_result["graph_edges_created"]),
        ),
    )
