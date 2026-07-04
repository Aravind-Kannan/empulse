"""Shared email-based identity auto-mapping helpers."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity
from app.schemas.identity import ProviderMember
from app.services.identity_mapping import PROVIDERS

logger = logging.getLogger(__name__)

_NOREPLY_SUFFIX = "@users.noreply.github.com"


def _is_usable_email(email: str | None) -> bool:
    if not email or not str(email).strip():
        return False
    return not str(email).strip().lower().endswith(_NOREPLY_SUFFIX)


def auto_map_provider_member_identities(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    members: list[ProviderMember],
) -> int:
    """
    Create high-confidence EmployeeIdentity rows from provider member emails.

    Skips ambiguous or conflicting mappings. Does not overwrite confirmed rows.
    """
    if provider not in PROVIDERS:
        return 0

    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    if not employees:
        return 0

    email_to_employee = {
        employee.email.strip().lower(): employee.id
        for employee in employees
        if employee.email and employee.email.strip()
    }

    existing_rows = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.provider == provider,
        )
        .all()
    )
    by_provider_id = {row.provider_username_or_id: row for row in existing_rows}
    by_employee_id = {row.employee_id: row for row in existing_rows}

    created = 0
    now = datetime.utcnow()
    for member in members:
        if not _is_usable_email(member.email):
            continue

        employee_id = email_to_employee.get(member.email.strip().lower())
        if not employee_id:
            continue

        provider_id = member.id.strip()
        if not provider_id:
            continue

        existing_for_employee = by_employee_id.get(employee_id)
        if existing_for_employee:
            if existing_for_employee.confidence == "confirmed":
                continue
            if existing_for_employee.provider_username_or_id != provider_id:
                continue

        existing_for_provider = by_provider_id.get(provider_id)
        if existing_for_provider:
            if existing_for_provider.employee_id != employee_id:
                continue
            continue

        row = EmployeeIdentity(
            tenant_id=tenant_id,
            employee_id=employee_id,
            provider=provider,
            provider_username_or_id=provider_id,
            provider_display_label=member.label.strip() or None,
            confidence="high",
            verified_at=now,
        )
        db.add(row)
        by_provider_id[provider_id] = row
        by_employee_id[employee_id] = row
        created += 1

    if created:
        db.commit()
        logger.info(
            "Auto-mapped %s %s identities for tenant %s",
            created,
            provider,
            tenant_id,
        )

    return created


def backfill_identity_display_labels(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    members: list[ProviderMember],
) -> int:
    """Attach human-readable labels to saved mappings when integrations are synced."""
    if provider not in PROVIDERS or not members:
        return 0

    labels_by_id = {
        member.id.strip(): member.label.strip()
        for member in members
        if member.id.strip() and member.label.strip()
    }
    if not labels_by_id:
        return 0

    rows = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.provider == provider,
        )
        .all()
    )
    updated = 0
    for row in rows:
        label = labels_by_id.get(row.provider_username_or_id.strip())
        if not label:
            continue
        if row.provider_display_label != label:
            row.provider_display_label = label
            updated += 1

    if updated:
        db.commit()
    return updated
