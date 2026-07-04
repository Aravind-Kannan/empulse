"""Notion documentation telemetry for ERA D dimension (Step 06)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee, NotionDocSnapshot
from app.services.notion_client import browser_notion_page_url
from app.services.notion_types import (
    NotionDocRecord,
    NotionEmployeeDocSignals,
    NotionTelemetrySnapshot,
)

STALE_RUNBOOK_DAYS = 180
LIVING_RUNBOOK_SECTIONS = (
    "Architecture decisions and constraints",
    "Incident history with root causes",
    "Vendor relationships and escalation paths",
    "Access maps and safe-change boundaries",
    "last_verified_at",
)


def utc_dt(value: datetime | None) -> datetime | None:
    """Normalize DB/API datetimes to timezone-aware UTC for comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return utc_dt(parsed)


def _component_has_github_activity(
    component_id: str,
    *,
    components_with_github_activity: set[str],
) -> bool:
    return component_id in components_with_github_activity


def _records_from_inventory(
    pages: list[dict],
    *,
    email_to_employee: dict[str, str],
    now: datetime,
) -> list[NotionDocRecord]:
    records: list[NotionDocRecord] = []
    stale_cutoff = now - timedelta(days=STALE_RUNBOOK_DAYS)

    for page in pages:
        last_edited = _parse_dt(page.get("last_edited_at")) or now
        owner_email = (page.get("owner_emails") or [None])[0]
        owner_employee_id = (
            email_to_employee.get(str(owner_email).lower())
            if owner_email
            else None
        )
        records.append(
            NotionDocRecord(
                page_id=str(page["page_id"]),
                title=str(page.get("title") or "Untitled"),
                page_url=browser_notion_page_url(
                    str(page["page_id"]),
                    str(page.get("page_url") or ""),
                ),
                last_edited_at=last_edited,
                component_id=page.get("component_id"),
                owner_employee_id=owner_employee_id,
                owner_email=owner_email,
                page_kind=str(page.get("page_kind") or "runbook"),
                is_archived=bool(page.get("is_archived")),
                is_ownership_template=page.get("page_kind") == "ownership_template",
                last_verified_at=_parse_dt(page.get("last_verified_at")),
            )
        )
        if records[-1].last_edited_at < stale_cutoff:
            pass
    return records


def compute_notion_telemetry(
    db: Session,
    tenant_id: uuid.UUID,
    docs: list[NotionDocRecord],
    *,
    people_expertise: list[dict] | None = None,
    components_with_github_activity: set[str] | None = None,
    now: datetime | None = None,
) -> NotionTelemetrySnapshot:
    now = now or datetime.now(UTC)
    stale_cutoff = now - timedelta(days=STALE_RUNBOOK_DAYS)
    github_active = components_with_github_activity or set()

    employees = (
        db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    )
    components = (
        db.query(Component).filter(Component.tenant_id == tenant_id).all()
    )
    assignments = (
        db.query(Assignment).filter(Assignment.tenant_id == tenant_id).all()
    )
    assigned_by_employee: dict[str, set[str]] = defaultdict(set)
    for assignment in assignments:
        assigned_by_employee[assignment.employee_id].add(assignment.component_id)

    email_to_employee = {employee.email.lower(): employee.id for employee in employees}

    docs_by_component: dict[str, list[NotionDocRecord]] = defaultdict(list)
    docs_by_owner: dict[str, list[NotionDocRecord]] = defaultdict(list)
    component_sources: dict[str, list[str]] = defaultdict(list)

    for doc in docs:
        if doc.is_archived:
            continue
        doc.last_edited_at = utc_dt(doc.last_edited_at) or now
        if doc.last_verified_at is not None:
            doc.last_verified_at = utc_dt(doc.last_verified_at)
        if doc.owner_employee_id:
            docs_by_owner[doc.owner_employee_id].append(doc)
        if doc.component_id:
            docs_by_component[doc.component_id].append(doc)
            component_sources[doc.component_id].append(f"Notion: {doc.title}")

    employee_signals: dict[str, NotionEmployeeDocSignals] = {}
    for employee in employees:
        owned_docs = docs_by_owner.get(employee.id, [])
        assigned_component_ids = assigned_by_employee.get(employee.id, set())
        without_docs = 0
        stale_count = 0
        for component_id in assigned_component_ids:
            linked = docs_by_component.get(component_id, [])
            if not linked and _component_has_github_activity(
                component_id, components_with_github_activity=github_active
            ):
                without_docs += 1
                continue
            if linked:
                freshest = max(linked, key=lambda row: row.last_edited_at)
                if (
                    freshest.last_edited_at < stale_cutoff
                    and _component_has_github_activity(
                        component_id, components_with_github_activity=github_active
                    )
                ):
                    stale_count += 1

        undocumented = 0
        if not owned_docs:
            active_assigned = [
                component_id
                for component_id in assigned_component_ids
                if _component_has_github_activity(
                    component_id, components_with_github_activity=github_active
                )
            ]
            if active_assigned:
                undocumented = min(3, len(active_assigned))

        employee_signals[employee.id] = NotionEmployeeDocSignals(
            employee_id=employee.id,
            pages_owned=len(owned_docs),
            components_without_docs=without_docs,
            stale_runbook_count=stale_count,
            undocumented_solved_incidents=undocumented,
            sole_critical_runbook_count=sum(
                1
                for doc in owned_docs
                if doc.page_kind == "runbook"
                and doc.component_id
                and len(docs_by_component.get(doc.component_id, [])) == 1
            ),
        )

    expertise_warnings: list[dict] = []
    tag_holders: dict[str, list[str]] = defaultdict(list)
    if people_expertise:
        for row in people_expertise:
            email = str(row.get("email", "")).lower()
            employee_id = email_to_employee.get(email)
            if not employee_id:
                continue
            for tag in row.get("tags") or []:
                tag_holders[str(tag).lower()].append(employee_id)
            signal = employee_signals.setdefault(
                employee_id,
                NotionEmployeeDocSignals(employee_id=employee_id),
            )
            signal.expertise_tags = sorted(set(row.get("tags") or []))

    for tag, holders in tag_holders.items():
        if len(holders) != 1:
            continue
        employee_id = holders[0]
        for component in components:
            criticality = getattr(component, "criticality", "tier2_core")
            if criticality != "tier1_revenue":
                continue
            if tag in component.name.lower() or component.name.lower() in tag:
                expertise_warnings.append(
                    {
                        "employee_id": employee_id,
                        "component_id": component.id,
                        "component_name": component.name,
                        "tag": tag,
                    }
                )

    return NotionTelemetrySnapshot(
        docs=docs,
        component_sources=dict(component_sources),
        employee_signals=employee_signals,
        expertise_sole_owner_warnings=expertise_warnings,
    )


def persist_notion_snapshots(
    db: Session,
    tenant_id: uuid.UUID,
    snapshot: NotionTelemetrySnapshot,
    *,
    computed_at: datetime | None = None,
) -> list[NotionDocSnapshot]:
    now = computed_at or datetime.now(UTC)
    stale_cutoff = now - timedelta(days=STALE_RUNBOOK_DAYS)

    db.query(NotionDocSnapshot).filter(
        NotionDocSnapshot.tenant_id == tenant_id
    ).delete(synchronize_session=False)

    rows: list[NotionDocSnapshot] = []
    for doc in snapshot.docs:
        if doc.is_archived:
            continue
        edited_at = utc_dt(doc.last_edited_at) or now
        verified_at = utc_dt(doc.last_verified_at)
        row = NotionDocSnapshot(
            tenant_id=tenant_id,
            page_id=doc.page_id,
            title=doc.title,
            page_url=doc.page_url,
            component_id=doc.component_id,
            owner_employee_id=doc.owner_employee_id,
            page_kind=doc.page_kind,
            last_edited_at=edited_at.replace(tzinfo=None),
            last_verified_at=verified_at.replace(tzinfo=None) if verified_at else None,
            is_stale=edited_at < stale_cutoff,
            is_archived=doc.is_archived,
            expertise_tags=doc.expertise_tags,
            computed_at=now,
        )
        db.add(row)
        rows.append(row)

    db.flush()
    return rows


def inventory_dicts_to_records(
    pages: list[dict],
    *,
    email_to_employee: dict[str, str],
    now: datetime | None = None,
) -> list[NotionDocRecord]:
    now = now or datetime.now(UTC)
    return _records_from_inventory(
        pages,
        email_to_employee=email_to_employee,
        now=now,
    )


def living_runbook_template_narrative() -> str:
    sections = "\n".join(f"- {section}" for section in LIVING_RUNBOOK_SECTIONS)
    return (
        "Living runbook / ownership transfer template sections:\n"
        f"{sections}\n"
        "Use these sections when generating ownership transfer pages for high D scores."
    )
