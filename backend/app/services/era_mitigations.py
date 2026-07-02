"""ERA mitigation rules, persistence, and evidence overlays (Step 12)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.operational import Employee, EraEvidenceMitigation
from app.schemas.era import EraEmployeeMetrics, EraEvidenceItem, EraMitigationItem
from app.services.era.evidence_ids import stable_evidence_id
from app.services.integration_config_store import get_github_config, get_jira_config

MITIGATION_STATUSES = frozenset({"open", "in_progress", "done", "dismissed"})


@dataclass(frozen=True)
class MitigationRule:
    name: str
    action: str
    priority: str
    link_template: str | None
    condition: Callable[..., bool]


def _has_backup(backup_candidate_count: int) -> bool:
    return backup_candidate_count > 0


def _build_rules() -> list[MitigationRule]:
    return [
        MitigationRule(
            name="pair_with_backup",
            action="Pair on next 2 PRs with backup engineer",
            priority="high",
            link_template="/settings/org-chart",
            condition=lambda metric, **ctx: (
                metric.dimensions is not None
                and metric.dimensions.knowledge > 70
                and _has_backup(ctx.get("backup_candidate_count", 0))
            ),
        ),
        MitigationRule(
            name="codeowners_backup",
            action="Add backup owner in CODEOWNERS",
            priority="critical",
            link_template="{github_repo}/settings/codeowners",
            condition=lambda metric, **ctx: (
                metric.dimensions is not None
                and metric.dimensions.knowledge > 70
                and not _has_backup(ctx.get("backup_candidate_count", 0))
            ),
        ),
        MitigationRule(
            name="runbook_update",
            action="Schedule runbook update sprint",
            priority="medium",
            link_template="{notion_runbook_url}",
            condition=lambda metric, **_ctx: (
                metric.dimensions is not None and metric.dimensions.documentation > 50
            ),
        ),
        MitigationRule(
            name="redistribute_jira",
            action="Redistribute Jira epics across team",
            priority="high",
            link_template="{jira_filter_url}",
            condition=lambda metric, **_ctx: (
                metric.dimensions is not None and metric.dimensions.operational > 60
            ),
        ),
        MitigationRule(
            name="manager_workload_review",
            action="Manager workload review — burnout signals detected",
            priority="medium",
            link_template=None,
            condition=lambda metric, **_ctx: bool(metric.departure_watchlist),
        ),
    ]


MITIGATION_RULES = _build_rules()


def _resolve_link(
    template: str | None,
    *,
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee | None,
) -> str | None:
    if not template:
        return None
    if template.startswith("/"):
        return template
    github_config = get_github_config(db, tenant_id)
    jira_config = get_jira_config(db, tenant_id)
    github_repo = ""
    if github_config and github_config.repository_url:
        github_repo = github_config.repository_url.rstrip("/")
    jira_filter_url = ""
    if jira_config and jira_config.site_url:
        jira_filter_url = f"{jira_config.site_url.rstrip('/')}/issues/?filter=-1"
    notion_runbook_url = "/settings/integrations"
    return (
        template.replace("{github_repo}", github_repo)
        .replace("{jira_filter_url}", jira_filter_url)
        .replace("{notion_runbook_url}", notion_runbook_url)
    )


def _suggested_mitigation_for_evidence(item: dict) -> str | None:
    dimension = item.get("dimension")
    severity = item.get("severity")
    if severity != "high":
        return None
    if dimension == "knowledge":
        return "Add backup owner in CODEOWNERS"
    if dimension == "documentation":
        return "Schedule runbook update sprint"
    if dimension == "operational":
        return "Redistribute Jira epics across team"
    if dimension == "burnout":
        return "Manager workload review — burnout signals detected"
    if dimension == "structural":
        return "Redistribute ownership across team"
    return None


def attach_suggested_mitigations(items: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for item in items:
        row = dict(item)
        suggestion = _suggested_mitigation_for_evidence(row)
        if suggestion:
            row["suggested_mitigation"] = suggestion
        enriched.append(row)
    return enriched


def _rule_evidence_id(action: str) -> str:
    return stable_evidence_id(dimension="mitigation", title=action, component_id=None)


def evaluate_mitigation_rules(
    metric: EraEmployeeMetrics,
    *,
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee | None,
    backup_candidate_count: int,
) -> list[EraMitigationItem]:
    items: list[EraMitigationItem] = []
    for rule in MITIGATION_RULES:
        if not rule.condition(metric, backup_candidate_count=backup_candidate_count):
            continue
        evidence_id = _rule_evidence_id(rule.action)
        items.append(
            EraMitigationItem(
                evidence_id=evidence_id,
                title=rule.action,
                priority=rule.priority,
                link=_resolve_link(
                    rule.link_template,
                    db=db,
                    tenant_id=tenant_id,
                    employee=employee,
                ),
                suggested_mitigation=rule.action,
                mitigation_status="open",
            )
        )
    return items


def _load_mitigation_map(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
) -> dict[str, EraEvidenceMitigation]:
    rows = (
        db.query(EraEvidenceMitigation)
        .filter(
            EraEvidenceMitigation.tenant_id == tenant_id,
            EraEvidenceMitigation.employee_id == employee_id,
        )
        .all()
    )
    return {row.evidence_id: row for row in rows}


def _overlay_row(
    item: EraMitigationItem,
    stored: EraEvidenceMitigation | None,
) -> EraMitigationItem:
    if stored is None:
        return item
    return item.model_copy(
        update={
            "mitigation_status": stored.mitigation_status,
            "suggested_mitigation": stored.suggested_mitigation or item.suggested_mitigation,
            "mitigation_assignee_id": stored.mitigation_assignee_id,
            "mitigation_due_date": (
                stored.mitigation_due_date.isoformat()
                if stored.mitigation_due_date
                else None
            ),
            "mitigation_notes": stored.mitigation_notes,
        }
    )


def apply_mitigation_overlays(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    evidence: list[dict],
    checklist: list[EraMitigationItem],
) -> tuple[list[dict], list[EraMitigationItem]]:
    stored = _load_mitigation_map(db, tenant_id, employee_id)
    enriched_evidence: list[dict] = []
    for item in evidence:
        row = dict(item)
        record = stored.get(row["id"])
        if record:
            row["mitigation_status"] = record.mitigation_status
            row["suggested_mitigation"] = record.suggested_mitigation or row.get(
                "suggested_mitigation"
            )
            row["mitigation_assignee_id"] = record.mitigation_assignee_id
            row["mitigation_due_date"] = (
                record.mitigation_due_date.isoformat()
                if record.mitigation_due_date
                else None
            )
            row["mitigation_notes"] = record.mitigation_notes
        elif row.get("suggested_mitigation") and not row.get("mitigation_status"):
            row["mitigation_status"] = "open"
        enriched_evidence.append(row)

    enriched_checklist = [_overlay_row(item, stored.get(item.evidence_id)) for item in checklist]
    return enriched_evidence, enriched_checklist


def ensure_mitigation_records(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    checklist: list[EraMitigationItem],
    evidence: list[dict],
) -> None:
    now = datetime.now(UTC)
    payloads: list[dict] = []
    for item in checklist:
        payloads.append(
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "evidence_id": item.evidence_id,
                "mitigation_status": item.mitigation_status or "open",
                "suggested_mitigation": item.suggested_mitigation,
                "mitigation_assignee_id": item.mitigation_assignee_id,
                "mitigation_due_date": item.mitigation_due_date,
                "mitigation_notes": item.mitigation_notes,
                "updated_at": now,
            }
        )
    for item in evidence:
        if not item.get("suggested_mitigation"):
            continue
        payloads.append(
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "evidence_id": item["id"],
                "mitigation_status": item.get("mitigation_status") or "open",
                "suggested_mitigation": item.get("suggested_mitigation"),
                "mitigation_assignee_id": item.get("mitigation_assignee_id"),
                "mitigation_due_date": item.get("mitigation_due_date"),
                "mitigation_notes": item.get("mitigation_notes"),
                "updated_at": now,
            }
        )

    seen: set[str] = set()
    for payload in payloads:
        evidence_id = payload["evidence_id"]
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        stmt = insert(EraEvidenceMitigation).values(**payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_era_evidence_mitigation",
            set_={
                "suggested_mitigation": payload["suggested_mitigation"],
                "updated_at": payload["updated_at"],
            },
        )
        db.execute(stmt)
    db.flush()


def update_evidence_mitigation(
    db: Session,
    tenant_id: uuid.UUID,
    employee_id: str,
    evidence_id: str,
    *,
    mitigation_status: str,
    assignee_id: str | None = None,
    due_date: date | None = None,
    notes: str | None = None,
    suggested_mitigation: str | None = None,
) -> EraEvidenceMitigation:
    if mitigation_status not in MITIGATION_STATUSES:
        raise ValueError(f"Invalid mitigation_status '{mitigation_status}'.")

    existing = (
        db.query(EraEvidenceMitigation)
        .filter(
            EraEvidenceMitigation.tenant_id == tenant_id,
            EraEvidenceMitigation.employee_id == employee_id,
            EraEvidenceMitigation.evidence_id == evidence_id,
        )
        .one_or_none()
    )
    now = datetime.now(UTC)
    if existing is None:
        row = EraEvidenceMitigation(
            tenant_id=tenant_id,
            employee_id=employee_id,
            evidence_id=evidence_id,
            mitigation_status=mitigation_status,
            suggested_mitigation=suggested_mitigation,
            mitigation_assignee_id=assignee_id,
            mitigation_due_date=due_date,
            mitigation_notes=notes,
            updated_at=now,
        )
        db.add(row)
    else:
        existing.mitigation_status = mitigation_status
        if assignee_id is not None:
            existing.mitigation_assignee_id = assignee_id
        if due_date is not None:
            existing.mitigation_due_date = due_date
        if notes is not None:
            existing.mitigation_notes = notes
        if suggested_mitigation is not None:
            existing.suggested_mitigation = suggested_mitigation
        existing.updated_at = now
        row = existing
    db.commit()
    db.refresh(row)
    return row


def count_open_mitigations(checklist: list[EraMitigationItem]) -> int:
    return sum(
        1
        for item in checklist
        if item.mitigation_status in {"open", "in_progress"}
    )


def evidence_item_from_mitigation(row: EraEvidenceMitigation) -> dict:
    return {
        "id": row.evidence_id,
        "dimension": "mitigation",
        "severity": "medium",
        "title": row.suggested_mitigation or row.evidence_id,
        "description": row.suggested_mitigation or "",
        "impact_points": 0.0,
        "sources": [],
        "synthetic": False,
        "mitigation_status": row.mitigation_status,
        "suggested_mitigation": row.suggested_mitigation,
        "mitigation_assignee_id": row.mitigation_assignee_id,
        "mitigation_due_date": (
            row.mitigation_due_date.isoformat() if row.mitigation_due_date else None
        ),
        "mitigation_notes": row.mitigation_notes,
    }
