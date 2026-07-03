from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.operational import Employee
from app.schemas.era import EraAnalyticsResponse, EraEmployeeDetailResponse
from app.schemas.era import (
    EraAlertAcknowledgeRequest,
    EraAlertItem,
    EraAlertsResponse,
    EraEvidenceMitigationPatchRequest,
    EraEvidenceMitigationPatchResponse,
    EraManagerRollupResponse,
    EraOpenP1IssuesResponse,
    EraReviewCadenceResponse,
    EraReviewNetworkResponse,
    EraSettingsResponse,
    EraSettingsUpdateRequest,
    EraTeamReviewCreateRequest,
    EraTeamReviewItem,
    EraTeamReviewsResponse,
    EraTeamRiskyChangesResponse,
)
from app.schemas.file_risk import EraHotspotsResponse, KraFileRiskResponse
from app.schemas.kra import (
    KraAnalyticsResponse,
    KraSummaryResponse,
)
from app.services.era_analytics import (
    get_era_employee_detail,
    get_era_manager_rollup,
    get_era_metrics,
    get_era_open_p1_issues,
    get_era_review_network,
    get_era_team_risky_changes,
    patch_era_evidence_mitigation,
)
from app.services.era_alerts import (
    acknowledge_era_alert,
    get_review_cadence,
    list_era_alerts,
    list_era_reviews,
    record_era_review,
    sync_era_alerts,
)
from app.services.era_settings_store import get_era_settings, save_era_settings
from app.services.github_file_risk import get_employee_hotspots, get_kra_file_risk
from app.services.kra_analytics import get_kra_graph
from app.services.kra_metrics import get_kra_summary
from app.tenancy import CurrentTenant

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/era", response_model=EraAnalyticsResponse)
def era_analytics(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraAnalyticsResponse:
    response = get_era_metrics(db, tenant)
    sync_era_alerts(db, tenant, demo_mode=response.demo_mode)
    return response


@router.get("/era/alerts", response_model=EraAlertsResponse)
def era_alerts(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    unacknowledged: bool = Query(default=False),
) -> EraAlertsResponse:
    demo_mode = db.query(Employee).filter(Employee.tenant_id == tenant.id).count() == 0
    sync_era_alerts(db, tenant, demo_mode=demo_mode)
    return list_era_alerts(db, tenant.id, unacknowledged=unacknowledged)


@router.post("/era/alerts/{alert_id}/acknowledge", response_model=EraAlertItem)
def era_acknowledge_alert(
    alert_id: int,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    payload: EraAlertAcknowledgeRequest | None = None,
) -> EraAlertItem:
    body = payload or EraAlertAcknowledgeRequest()
    row = acknowledge_era_alert(
        db,
        tenant.id,
        alert_id,
        acknowledged_by=body.acknowledged_by,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return row


@router.get("/era/reviews", response_model=EraTeamReviewsResponse)
def era_reviews(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraTeamReviewsResponse:
    return list_era_reviews(db, tenant.id)


@router.get("/era/review-cadence", response_model=EraReviewCadenceResponse)
def era_review_cadence(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraReviewCadenceResponse:
    return get_review_cadence(db, tenant.id)


@router.post("/era/reviews", response_model=EraTeamReviewItem)
def era_create_review(
    payload: EraTeamReviewCreateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraTeamReviewItem:
    return record_era_review(db, tenant, payload)


@router.get("/era/settings", response_model=EraSettingsResponse)
def era_settings_get(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraSettingsResponse:
    settings = get_era_settings(db, tenant.id)
    return EraSettingsResponse(**settings)


@router.put("/era/settings", response_model=EraSettingsResponse)
def era_settings_put(
    payload: EraSettingsUpdateRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraSettingsResponse:
    patch = payload.model_dump(exclude_unset=True)
    settings = save_era_settings(db, tenant.id, patch)
    return EraSettingsResponse(**settings)


@router.patch(
    "/era/evidence/{evidence_id}",
    response_model=EraEvidenceMitigationPatchResponse,
)
def patch_era_evidence_mitigation_route(
    evidence_id: str,
    payload: EraEvidenceMitigationPatchRequest,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraEvidenceMitigationPatchResponse:
    try:
        row = patch_era_evidence_mitigation(
            db,
            tenant,
            evidence_id,
            employee_id=payload.employee_id,
            mitigation_status=payload.mitigation_status,
            assignee_id=payload.assignee_id,
            due_date=payload.due_date,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Employee '{payload.employee_id}' not found.",
        )
    return EraEvidenceMitigationPatchResponse(
        evidence_id=row.evidence_id,
        employee_id=row.employee_id,
        mitigation_status=row.mitigation_status,
        suggested_mitigation=row.suggested_mitigation,
        mitigation_assignee_id=row.mitigation_assignee_id,
        mitigation_due_date=(
            row.mitigation_due_date.isoformat() if row.mitigation_due_date else None
        ),
        mitigation_notes=row.mitigation_notes,
        updated_at=row.updated_at,
    )


@router.get("/era/open-p1-issues", response_model=EraOpenP1IssuesResponse)
def era_open_p1_issues(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraOpenP1IssuesResponse:
    return get_era_open_p1_issues(db, tenant)


@router.get("/era/rollup", response_model=EraManagerRollupResponse)
def era_manager_rollup(
    manager_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraManagerRollupResponse:
    payload = get_era_manager_rollup(db, tenant, manager_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Manager '{manager_id}' not found.")
    return payload


@router.get("/era/{employee_id}/review-network", response_model=EraReviewNetworkResponse)
def era_employee_review_network(
    employee_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraReviewNetworkResponse:
    payload = get_era_review_network(db, tenant, employee_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' not found.")
    return payload


@router.get("/team/risky-changes", response_model=EraTeamRiskyChangesResponse)
def era_team_risky_changes(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    since: str = Query(default="90d"),
) -> EraTeamRiskyChangesResponse:
    return get_era_team_risky_changes(db, tenant, since=since)


@router.get("/era/{employee_id}/hotspots", response_model=EraHotspotsResponse)
def era_employee_hotspots(
    employee_id: str,
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> EraHotspotsResponse:
    return EraHotspotsResponse(**get_employee_hotspots(db, tenant.id, employee_id))


@router.get("/kra/file-risk", response_model=KraFileRiskResponse)
def kra_file_risk(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
    component_id: str | None = Query(default=None),
) -> KraFileRiskResponse:
    return KraFileRiskResponse(**get_kra_file_risk(db, tenant.id, component_id=component_id))


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


@router.get("/kra/summary", response_model=KraSummaryResponse)
def kra_summary(
    tenant: CurrentTenant,
    db: Session = Depends(get_db),
) -> KraSummaryResponse:
    return get_kra_summary(db, tenant.id)
