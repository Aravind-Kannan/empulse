"""Shared email-based identity auto-mapping helpers."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity
from app.schemas.identity import ProviderMember
from app.services.identity_mapping import (
    PROVIDERS,
    guess_provider_member_id,
    mapping_match_confidence,
    provider_member_display_label,
)

logger = logging.getLogger(__name__)

_GITHUB_NOREPLY_SUFFIX = "@users.noreply.github.com"


def is_usable_roster_email(email: str | None) -> bool:
    """True when email can seed org-chart roster rows (excludes GitHub noreply placeholders)."""
    if not email or not str(email).strip():
        return False
    return not str(email).strip().lower().endswith(_GITHUB_NOREPLY_SUFFIX)


def auto_map_provider_member_identities(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    members: list[ProviderMember],
) -> int:
    """
    Create EmployeeIdentity rows by matching roster employees to provider members.

    Uses email-first matching, then normalized name/login heuristics (same rules
    as reconciliation guesses). Skips ambiguous or conflicting mappings and
    does not overwrite confirmed rows.
    """
    if provider not in PROVIDERS or not members:
        return 0

    employees = db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    if not employees:
        return 0

    members_by_id = {
        member.id.strip(): member for member in members if member.id and member.id.strip()
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
    for employee in employees:
        existing_for_employee = by_employee_id.get(employee.id)
        if existing_for_employee:
            if existing_for_employee.confidence == "confirmed":
                continue
            continue

        guessed_id = guess_provider_member_id(employee, members)
        if not guessed_id:
            continue

        member = members_by_id.get(guessed_id)
        if not member:
            continue

        provider_id = guessed_id.strip()
        if not provider_id:
            continue

        existing_for_provider = by_provider_id.get(provider_id)
        if existing_for_provider:
            if existing_for_provider.employee_id != employee.id:
                continue
            continue

        row = EmployeeIdentity(
            tenant_id=tenant_id,
            employee_id=employee.id,
            provider=provider,
            provider_username_or_id=provider_id,
            provider_display_label=provider_member_display_label(member),
            confidence=mapping_match_confidence(employee, member),
            verified_at=now,
        )
        db.add(row)
        by_provider_id[provider_id] = row
        by_employee_id[employee.id] = row
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
