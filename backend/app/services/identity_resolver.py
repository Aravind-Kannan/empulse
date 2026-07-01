"""Resolve external provider users to canonical Employee records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity
from app.schemas.identity import ProviderMember
from app.services.identity_mapping import MOCK_PROVIDER_MEMBERS, PROVIDERS

IdentityConfidence = Literal["confirmed", "high", "medium", "low", "none"]
ATTRIBUTABLE_CONFIDENCE: frozenset[str] = frozenset({"confirmed", "high", "medium"})


@dataclass(frozen=True)
class ResolveResult:
    employee_id: str | None
    confidence: IdentityConfidence
    match_method: str | None
    identity_warning: bool = False


def should_attribute(result: ResolveResult) -> bool:
    return result.confidence in ATTRIBUTABLE_CONFIDENCE


def is_identity_gating_active(db: Session, tenant_id: uuid.UUID) -> bool:
    """Gate attribution when the tenant has persisted employees (non-demo path)."""
    return (
        db.query(Employee.id)
        .filter(Employee.tenant_id == tenant_id)
        .limit(1)
        .first()
        is not None
    )


def _find_provider_member(provider: str, provider_user_id: str) -> ProviderMember | None:
    for member in MOCK_PROVIDER_MEMBERS.get(provider, []):
        if member.id == provider_user_id:
            return member
    return None


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _fuzzy_name_matches(employees: list[Employee], label: str) -> list[Employee]:
    label_slug = label.lower().replace("-", "").replace(".", "").replace("@", "").replace(" ", "")
    if not label_slug:
        return []
    matches: list[Employee] = []
    for employee in employees:
        name_slug = employee.name.lower().replace(" ", "")
        if name_slug in label_slug or label_slug in name_slug:
            matches.append(employee)
    return matches


def resolve_employee(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    provider_user_id: str,
    *,
    email_hint: str | None = None,
) -> ResolveResult:
    """
    Resolve a provider user to a canonical employee.

    Lookup order:
    1. Saved EmployeeIdentity mapping (confirmed)
    2. Email exact match via hint or provider member profile (high)
    3. Fuzzy name match from provider member label (medium, single match only)
    4. No match (none) — caller should quarantine
    """
    if provider not in PROVIDERS:
        return ResolveResult(None, "none", "unknown_provider")

    provider_user_id = provider_user_id.strip()
    if not provider_user_id:
        return ResolveResult(None, "none", "empty_provider_user_id")

    saved = (
        db.query(EmployeeIdentity)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.provider == provider,
            EmployeeIdentity.provider_username_or_id == provider_user_id,
        )
        .one_or_none()
    )
    if saved:
        confidence: IdentityConfidence = (
            saved.confidence if saved.confidence in ATTRIBUTABLE_CONFIDENCE else "confirmed"
        )
        return ResolveResult(
            saved.employee_id,
            confidence,
            "saved_mapping",
            identity_warning=confidence == "medium",
        )

    tenant_employees = (
        db.query(Employee).filter(Employee.tenant_id == tenant_id).all()
    )

    emails_to_try: list[str] = []
    if email_hint and email_hint.strip():
        emails_to_try.append(_normalize_email(email_hint))
    member = _find_provider_member(provider, provider_user_id)
    if member and member.email:
        emails_to_try.append(_normalize_email(member.email))

    seen_emails: set[str] = set()
    for email in emails_to_try:
        if email in seen_emails:
            continue
        seen_emails.add(email)
        matches = [
            employee
            for employee in tenant_employees
            if _normalize_email(employee.email) == email
        ]
        if len(matches) == 1:
            return ResolveResult(matches[0].id, "high", "email_match")
        if len(matches) > 1:
            return ResolveResult(None, "none", "ambiguous_email")

    if member:
        fuzzy_matches = _fuzzy_name_matches(tenant_employees, member.label)
        if len(fuzzy_matches) == 1:
            return ResolveResult(
                fuzzy_matches[0].id,
                "medium",
                "fuzzy_name",
                identity_warning=True,
            )
        if len(fuzzy_matches) > 1:
            return ResolveResult(None, "none", "ambiguous_fuzzy_name")

    return ResolveResult(None, "none", "no_match")


def resolve_author_employee_id(
    db: Session,
    tenant_id: uuid.UUID,
    provider: str,
    provider_user_id: str,
    *,
    email_hint: str | None = None,
    demo_fallback_employee_id: str | None = None,
    quarantine_event_type: str = "activity",
    quarantine_payload: dict | None = None,
) -> str | None:
    """
    Resolve author for telemetry/sync. Returns employee_id or None.
    Quarantines unmapped activity when gating is active.
    """
    from app.services.unmapped_activity import record_unmapped_activity

    if not is_identity_gating_active(db, tenant_id):
        return demo_fallback_employee_id

    result = resolve_employee(
        db,
        tenant_id,
        provider,
        provider_user_id,
        email_hint=email_hint,
    )
    if should_attribute(result):
        return result.employee_id

    member = _find_provider_member(provider, provider_user_id)
    record_unmapped_activity(
        db,
        tenant_id,
        provider=provider,
        provider_user_id=provider_user_id,
        event_type=quarantine_event_type,
        provider_label=member.label if member else provider_user_id,
        payload=quarantine_payload,
    )
    return None
