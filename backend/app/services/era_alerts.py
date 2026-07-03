"""ERA proactive alerts and team review cadence (Step 17)."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable
from urllib import error, request

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.operational import Component, EraAlert, EraRiskSnapshot, EraTeamReview, FileRiskSnapshot
from app.schemas.era import (
    EraAlertItem,
    EraAlertsResponse,
    EraReviewCadenceResponse,
    EraTeamReviewCreateRequest,
    EraTeamReviewItem,
    EraTeamReviewsResponse,
)
from app.services.era.metadata import STALE_SYNC_HOURS
from app.services.era_settings_store import get_era_settings
from app.services.integration_config_store import get_github_config, get_jira_config
from app.services.integration_telemetry import (
    get_sync_freshness,
    get_unassigned_p1_by_component,
    has_github_sync,
    has_jira_sync,
    is_github_spof,
)
from app.services.unmapped_activity import get_total_unmapped_count, reconcile_and_prune_unmapped_activity

logger = logging.getLogger(__name__)

DEDUP_WINDOW_HOURS = 24
RE_ALERT_DAYS = 7
SLACK_WEBHOOK_RULES = frozenset({"spof_tier1"})


@dataclass(frozen=True)
class AlertCandidate:
    rule_id: str
    severity: str
    title: str
    description: str
    dedupe_key: str
    employee_id: str | None = None
    component_id: str | None = None
    evidence_id: str | None = None


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _should_create_alert(db: Session, tenant_id: uuid.UUID, dedupe_key: str) -> bool:
    latest = (
        db.query(EraAlert)
        .filter(
            EraAlert.tenant_id == tenant_id,
            EraAlert.dedupe_key == dedupe_key,
        )
        .order_by(EraAlert.created_at.desc())
        .first()
    )
    if latest is None:
        return True
    now = datetime.now(UTC)
    created = _aware(latest.created_at)
    if latest.acknowledged_at is None:
        if now - created < timedelta(hours=DEDUP_WINDOW_HOURS):
            return False
        return False
    acknowledged = _aware(latest.acknowledged_at)
    if now - acknowledged < timedelta(days=RE_ALERT_DAYS):
        return False
    if now - created < timedelta(hours=DEDUP_WINDOW_HOURS):
        return False
    return True


def _evaluate_spof_tier1(db: Session, tenant_id: uuid.UUID) -> list[AlertCandidate]:
    if not has_github_sync():
        return []
    components = (
        db.query(Component)
        .filter(
            Component.tenant_id == tenant_id,
            Component.criticality == "tier1_revenue",
        )
        .all()
    )
    candidates: list[AlertCandidate] = []
    for component in components:
        if not is_github_spof(component.id):
            continue
        candidates.append(
            AlertCandidate(
                rule_id="spof_tier1",
                severity="critical",
                title=f"New SPOF on {component.name} (tier1)",
                description=(
                    f"{component.name} is a tier-1 revenue component with a single "
                    "active owner in GitHub — schedule cross-training and backup coverage."
                ),
                component_id=component.id,
                dedupe_key=f"spof_tier1:{component.id}",
            )
        )
    return candidates


def _evaluate_critical_file(db: Session, tenant_id: uuid.UUID) -> list[AlertCandidate]:
    rows = (
        db.query(FileRiskSnapshot)
        .filter(
            FileRiskSnapshot.tenant_id == tenant_id,
            FileRiskSnapshot.quadrant == "critical",
        )
        .order_by(FileRiskSnapshot.churn_score.desc())
        .limit(25)
        .all()
    )
    candidates: list[AlertCandidate] = []
    for row in rows:
        candidates.append(
            AlertCandidate(
                rule_id="critical_file",
                severity="high",
                title=f"Critical file hotspot — {row.file_path}",
                description=(
                    f"File entered the critical risk quadrant (churn {row.churn_score}, "
                    f"bus factor {row.bus_factor}). Review ownership and review coverage."
                ),
                component_id=row.component_id,
                employee_id=row.primary_owner_employee_id,
                dedupe_key=f"critical_file:{row.component_id}:{row.file_path}",
            )
        )
    return candidates


def _evaluate_unassigned_p1(db: Session, tenant_id: uuid.UUID) -> list[AlertCandidate]:
    if not has_jira_sync():
        return []
    component_names = {
        row.id: row.name
        for row in db.query(Component)
        .filter(Component.tenant_id == tenant_id)
        .all()
    }
    candidates: list[AlertCandidate] = []
    for component_id, issues in get_unassigned_p1_by_component().items():
        component_name = component_names.get(component_id, component_id)
        candidates.append(
            AlertCandidate(
                rule_id="unassigned_p1",
                severity="high",
                title=f"Unassigned P1 on {component_name}",
                description=(
                    f"{len(issues)} unassigned high-priority bug(s) on {component_name} "
                    "— triage ownership in Jira."
                ),
                component_id=component_id,
                dedupe_key=f"unassigned_p1:{component_id}",
            )
        )
    return candidates


def _evaluate_identity_gap(db: Session, tenant_id: uuid.UUID, threshold: int) -> list[AlertCandidate]:
    reconcile_and_prune_unmapped_activity(db, tenant_id, commit=True)
    unmapped = get_total_unmapped_count(db, tenant_id)
    if unmapped <= threshold:
        return []
    return [
        AlertCandidate(
            rule_id="identity_gap",
            severity="medium",
            title="Identity mapping gaps detected",
            description=(
                f"{unmapped} unmapped integration identities are quarantined — "
                "reconcile mappings before ERA scores can attribute activity."
            ),
            dedupe_key="identity_gap:tenant",
        )
    ]


def _integration_configured(db: Session, tenant_id: uuid.UUID, provider: str) -> bool:
    if provider == "github":
        return bool(get_github_config(db, tenant_id))
    if provider == "jira":
        return bool(get_jira_config(db, tenant_id))
    return False


def _evaluate_stale_sync(db: Session, tenant_id: uuid.UUID) -> list[AlertCandidate]:
    now = datetime.now(UTC)
    freshness = get_sync_freshness()
    candidates: list[AlertCandidate] = []
    for provider in ("github", "jira", "slack", "notion"):
        if not _integration_configured(db, tenant_id, provider):
            continue
        synced_at = freshness.get(provider)
        if not synced_at:
            candidates.append(
                AlertCandidate(
                    rule_id="stale_sync",
                    severity="medium",
                    title=f"{provider.title()} sync pending",
                    description=(
                        f"{provider.title()} is configured but has not completed a sync yet."
                    ),
                    dedupe_key=f"stale_sync:{provider}:pending",
                )
            )
            continue
        synced = datetime.fromisoformat(synced_at)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        if now - synced > timedelta(hours=STALE_SYNC_HOURS):
            hours = int((now - synced).total_seconds() // 3600)
            candidates.append(
                AlertCandidate(
                    rule_id="stale_sync",
                    severity="medium",
                    title=f"{provider.title()} sync stale ({hours}h)",
                    description=(
                        f"Last {provider.title()} sync was {hours} hours ago — "
                        "ERA signals may be outdated."
                    ),
                    dedupe_key=f"stale_sync:{provider}:stale",
                )
            )
    return candidates


def evaluate_alert_candidates(db: Session, tenant_id: uuid.UUID) -> list[AlertCandidate]:
    settings = get_era_settings(db, tenant_id)
    evaluators: list[Callable[[], list[AlertCandidate]]] = [
        lambda: _evaluate_spof_tier1(db, tenant_id),
        lambda: _evaluate_critical_file(db, tenant_id),
        lambda: _evaluate_unassigned_p1(db, tenant_id),
        lambda: _evaluate_identity_gap(db, tenant_id, int(settings["unmapped_threshold"])),
        lambda: _evaluate_stale_sync(db, tenant_id),
    ]
    candidates: list[AlertCandidate] = []
    for evaluate in evaluators:
        candidates.extend(evaluate())
    return candidates


def _team_slack_message(alerts: list[EraAlert]) -> str:
    spof = [alert for alert in alerts if alert.rule_id == "spof_tier1"]
    critical_files = [alert for alert in alerts if alert.rule_id == "critical_file"]
    parts = ["ERA team alert summary"]
    if spof:
        parts.append(f"{len(spof)} tier-1 SPOF component(s)")
    if critical_files:
        parts.append(f"{len(critical_files)} critical file hotspot(s)")
    frontend = get_settings().frontend_url.rstrip("/")
    parts.append(f"View: {frontend}/era")
    return " — ".join(parts)


def _post_slack_webhook(webhook_url: str, text: str) -> bool:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return 200 <= response.status < 300
    except (error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("ERA Slack webhook failed: %s", exc)
        return False


def _maybe_send_slack_webhook(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    demo_mode: bool,
    created_alerts: list[EraAlert],
) -> None:
    if demo_mode or not created_alerts:
        return
    settings = get_era_settings(db, tenant_id)
    if not settings.get("slack_webhook_enabled"):
        return
    webhook_url = str(settings.get("slack_webhook_url", "")).strip()
    if not webhook_url:
        return
    webhook_candidates = [
        alert for alert in created_alerts if alert.rule_id in SLACK_WEBHOOK_RULES
    ]
    if not webhook_candidates:
        return
    text = _team_slack_message(webhook_candidates)
    if _post_slack_webhook(webhook_url, text):
        now = datetime.now(UTC)
        for alert in webhook_candidates:
            alert.webhook_sent_at = now
        db.commit()


def sync_era_alerts(
    db: Session,
    tenant,
    *,
    demo_mode: bool = False,
) -> list[EraAlert]:
    created: list[EraAlert] = []
    for candidate in evaluate_alert_candidates(db, tenant.id):
        if not _should_create_alert(db, tenant.id, candidate.dedupe_key):
            continue
        row = EraAlert(
            tenant_id=tenant.id,
            rule_id=candidate.rule_id,
            severity=candidate.severity,
            title=candidate.title,
            description=candidate.description,
            employee_id=candidate.employee_id,
            component_id=candidate.component_id,
            evidence_id=candidate.evidence_id,
            dedupe_key=candidate.dedupe_key,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        created.append(row)
    if created:
        db.commit()
        for row in created:
            db.refresh(row)
        _maybe_send_slack_webhook(db, tenant.id, demo_mode=demo_mode, created_alerts=created)
    return created


def _alert_to_item(row: EraAlert) -> EraAlertItem:
    return EraAlertItem(
        id=row.id,
        rule_id=row.rule_id,
        severity=row.severity,
        title=row.title,
        description=row.description,
        employee_id=row.employee_id,
        component_id=row.component_id,
        evidence_id=row.evidence_id,
        created_at=row.created_at,
        acknowledged_at=row.acknowledged_at,
        acknowledged_by=row.acknowledged_by,
    )


def list_era_alerts(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    unacknowledged: bool = False,
) -> EraAlertsResponse:
    reconcile_and_prune_unmapped_activity(db, tenant_id, commit=True)
    query = db.query(EraAlert).filter(EraAlert.tenant_id == tenant_id)
    if unacknowledged:
        query = query.filter(EraAlert.acknowledged_at.is_(None))
    rows = query.order_by(EraAlert.created_at.desc()).limit(100).all()
    return EraAlertsResponse(
        computed_at=datetime.now(UTC),
        alerts=[_alert_to_item(row) for row in rows],
        unacknowledged_count=sum(1 for row in rows if row.acknowledged_at is None),
    )


def acknowledge_era_alert(
    db: Session,
    tenant_id: uuid.UUID,
    alert_id: int,
    *,
    acknowledged_by: str | None = None,
) -> EraAlertItem | None:
    row = (
        db.query(EraAlert)
        .filter(EraAlert.tenant_id == tenant_id, EraAlert.id == alert_id)
        .one_or_none()
    )
    if row is None:
        return None
    if row.acknowledged_at is None:
        row.acknowledged_at = datetime.now(UTC)
        row.acknowledged_by = acknowledged_by
        db.commit()
        db.refresh(row)
    return _alert_to_item(row)


def _review_to_item(row: EraTeamReview) -> EraTeamReviewItem:
    return EraTeamReviewItem(
        id=row.id,
        reviewed_at=row.reviewed_at,
        reviewer_user_id=row.reviewer_user_id,
        notes=row.notes,
        snapshot_avg_risk=row.snapshot_avg_risk,
        delta_since_last=row.delta_since_last,
    )


def list_era_reviews(db: Session, tenant_id: uuid.UUID) -> EraTeamReviewsResponse:
    rows = (
        db.query(EraTeamReview)
        .filter(EraTeamReview.tenant_id == tenant_id)
        .order_by(EraTeamReview.reviewed_at.desc())
        .limit(24)
        .all()
    )
    return EraTeamReviewsResponse(
        computed_at=datetime.now(UTC),
        reviews=[_review_to_item(row) for row in rows],
    )


def get_review_cadence(db: Session, tenant_id: uuid.UUID) -> EraReviewCadenceResponse:
    settings = get_era_settings(db, tenant_id)
    cadence_days = int(settings.get("review_cadence_days", 30))
    latest = (
        db.query(EraTeamReview)
        .filter(EraTeamReview.tenant_id == tenant_id)
        .order_by(EraTeamReview.reviewed_at.desc())
        .first()
    )
    if latest is None:
        return EraReviewCadenceResponse(
            computed_at=datetime.now(UTC),
            last_reviewed_at=None,
            days_since_last_review=None,
            review_overdue=True,
            review_cadence_days=cadence_days,
            snapshot_avg_risk=None,
        )
    reviewed_at = _aware(latest.reviewed_at)
    days_since = (datetime.now(UTC) - reviewed_at).days
    return EraReviewCadenceResponse(
        computed_at=datetime.now(UTC),
        last_reviewed_at=latest.reviewed_at,
        days_since_last_review=days_since,
        review_overdue=days_since > cadence_days,
        review_cadence_days=cadence_days,
        snapshot_avg_risk=latest.snapshot_avg_risk,
    )


def record_era_review(
    db: Session,
    tenant,
    payload: EraTeamReviewCreateRequest,
) -> EraTeamReviewItem:
    from app.services.era_snapshots import _utc_today

    today = _utc_today()
    rows = (
        db.query(EraRiskSnapshot.risk_factor_score)
        .filter(
            EraRiskSnapshot.tenant_id == tenant.id,
            EraRiskSnapshot.snapshot_date == today,
        )
        .all()
    )
    if rows:
        avg_risk = round(sum(score for (score,) in rows) / len(rows), 1)
    else:
        avg_risk = 0.0

    previous = (
        db.query(EraTeamReview)
        .filter(EraTeamReview.tenant_id == tenant.id)
        .order_by(EraTeamReview.reviewed_at.desc())
        .first()
    )
    delta = None
    if previous is not None:
        delta = round(avg_risk - previous.snapshot_avg_risk, 1)

    row = EraTeamReview(
        tenant_id=tenant.id,
        reviewed_at=datetime.now(UTC),
        reviewer_user_id=payload.reviewer_user_id,
        notes=payload.notes,
        snapshot_avg_risk=avg_risk,
        delta_since_last=delta,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _review_to_item(row)
