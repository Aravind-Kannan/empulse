from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity, UnmappedActivity
from app.schemas.identity import (
    EmployeeIdentityMapping,
    EmployeeIdentityRecord,
    EmployeeIdentityRow,
    IdentityReconciliationResponse,
    ProviderMember,
)
from app.services.unmapped_activity import (
    get_total_unmapped_count,
    get_unmapped_counts_by_provider,
)

PROVIDERS = ("github", "jira", "slack", "notion")

MOCK_PROVIDER_MEMBERS: dict[str, list[ProviderMember]] = {
    "github": [
        ProviderMember(id="gh-alicechen", label="alicechen", email="alice.chen@acme.com"),
        ProviderMember(id="gh-benrivera", label="benrivera-dev", email="ben.rivera@acme.com"),
        ProviderMember(id="gh-carapatel", label="cara-patel", email="cara.patel@acme.com"),
        ProviderMember(id="gh-dalvarezz", label="dalvarezz", email="diego.alvarez@acme.com"),
        ProviderMember(id="gh-elena-k", label="elena-kowalski", email="elena.kowalski@acme.com"),
        ProviderMember(id="gh-frankosei", label="fosei", email="frank.osei@acme.com"),
        ProviderMember(id="gh-ext-001", label="contractor-bot", email=None),
    ],
    "jira": [
        ProviderMember(id="jira-alice", label="alice.chen@acme.com", email="alice.chen@acme.com"),
        ProviderMember(id="jira-ben", label="ben.rivera@acme.com", email="ben.rivera@acme.com"),
        ProviderMember(id="jira-cara", label="cara.patel@acme.com", email="cara.patel@acme.com"),
        ProviderMember(id="jira-diego", label="diego.alvarez@acme.com", email="diego.alvarez@acme.com"),
        ProviderMember(id="jira-elena", label="elena.kowalski@acme.com", email="elena.kowalski@acme.com"),
        ProviderMember(id="jira-frank", label="frank.osei@acme.com", email="frank.osei@acme.com"),
    ],
    "slack": [
        ProviderMember(id="U01ALICE", label="@alice.chen", email="alice.chen@acme.com"),
        ProviderMember(id="U02BEN", label="@ben.rivera", email="ben.rivera@acme.com"),
        ProviderMember(id="U03CARA", label="@cara", email="cara.patel@acme.com"),
        ProviderMember(id="U04DIEGO", label="@diego.a", email="diego.alvarez@acme.com"),
        ProviderMember(id="U05ELENA", label="@elena", email="elena.kowalski@acme.com"),
        ProviderMember(id="U06FRANK", label="@frank.osei", email="frank.osei@acme.com"),
    ],
    "notion": [
        ProviderMember(id="notion-alice", label="Alice Chen", email="alice.chen@acme.com"),
        ProviderMember(id="notion-ben", label="Ben Rivera", email="ben.rivera@acme.com"),
        ProviderMember(id="notion-cara", label="Cara Patel", email="cara.patel@acme.com"),
        ProviderMember(id="notion-diego", label="Diego Alvarez", email="diego.alvarez@acme.com"),
        ProviderMember(id="notion-elena", label="Elena Kowalski", email="elena.kowalski@acme.com"),
        ProviderMember(id="notion-frank", label="Frank Osei", email="frank.osei@acme.com"),
    ],
}


def get_provider_members(
    provider: str,
    db: Session | None = None,
    tenant_id: uuid.UUID | None = None,
) -> list[ProviderMember]:
    members, _ = load_provider_members_with_warning(provider, db, tenant_id)
    return members


def load_provider_members_with_warning(
    provider: str,
    db: Session | None,
    tenant_id: uuid.UUID | None,
) -> tuple[list[ProviderMember], str | None]:
    if provider not in MOCK_PROVIDER_MEMBERS:
        return [], None
    fallback = MOCK_PROVIDER_MEMBERS[provider]
    if db is not None and tenant_id is not None:
        from app.services.provider_members import get_provider_members_for_tenant

        return get_provider_members_for_tenant(
            db,
            tenant_id,
            provider,
            fallback_members=fallback,
        )
    return fallback, None


def list_identity_mappings(db: Session, tenant) -> list[EmployeeIdentityRecord]:
    rows = (
        db.query(EmployeeIdentity)
        .filter(EmployeeIdentity.tenant_id == tenant.id)
        .order_by(EmployeeIdentity.employee_id)
        .all()
    )
    return [
        EmployeeIdentityRecord(
            id=row.id,
            employee_id=row.employee_id,
            provider=row.provider,
            provider_username_or_id=row.provider_username_or_id,
        )
        for row in rows
    ]


def _guess_mapping(
    employee: Employee,
    provider: str,
    members: list[ProviderMember],
) -> str | None:
    email = employee.email.lower()
    for member in members:
        if member.email and member.email.lower() == email:
            return member.id
    name_slug = employee.name.lower().replace(" ", "")
    for member in members:
        if name_slug in member.label.lower().replace("-", "").replace(".", ""):
            return member.id
    return None


def get_reconciliation(
    db: Session,
    tenant,
    connected_providers: list[str] | None = None,
) -> IdentityReconciliationResponse:
    active_providers = [
        provider for provider in (connected_providers or list(PROVIDERS)) if provider in PROVIDERS
    ]
    employees = (
        db.query(Employee)
        .filter(Employee.tenant_id == tenant.id)
        .order_by(Employee.name)
        .all()
    )
    existing = (
        db.query(EmployeeIdentity)
        .filter(EmployeeIdentity.tenant_id == tenant.id)
        .all()
    )
    mapping_index: dict[tuple[str, str], str] = {
        (row.employee_id, row.provider): row.provider_username_or_id for row in existing
    }

    rows: list[EmployeeIdentityRow] = []
    provider_members: dict[str, list[ProviderMember]] = {}
    provider_warnings: dict[str, str] = {}
    for provider in active_providers:
        members, warning = load_provider_members_with_warning(provider, db, tenant.id)
        provider_members[provider] = members
        if warning:
            provider_warnings[provider] = warning
    for employee in employees:
        mappings: dict[str, str | None] = {}
        for provider in active_providers:
            saved = mapping_index.get((employee.id, provider))
            members = provider_members.get(provider, [])
            mappings[provider] = saved or _guess_mapping(employee, provider, members)
        rows.append(
            EmployeeIdentityRow(
                employee_id=employee.id,
                name=employee.name,
                email=employee.email,
                role=employee.role,
                mappings=mappings,
            )
        )

    return IdentityReconciliationResponse(
        employees=rows,
        provider_members=provider_members,
        connected_providers=active_providers,
        provider_warnings=provider_warnings,
        unmapped_activity=get_unmapped_counts_by_provider(db, tenant.id),
        total_unmapped_count=get_total_unmapped_count(db, tenant.id),
    )


def save_identity_mappings(
    db: Session,
    tenant,
    mappings: list[EmployeeIdentityMapping],
) -> list[EmployeeIdentityRecord]:
    saved: list[EmployeeIdentityRecord] = []

    for mapping in mappings:
        if mapping.provider not in PROVIDERS:
            continue

        row = (
            db.query(EmployeeIdentity)
            .filter(
                EmployeeIdentity.employee_id == mapping.employee_id,
                EmployeeIdentity.provider == mapping.provider,
                EmployeeIdentity.tenant_id == tenant.id,
            )
            .one_or_none()
        )

        if not mapping.provider_username_or_id.strip():
            if row:
                db.delete(row)
            continue

        value = mapping.provider_username_or_id.strip()
        now = datetime.utcnow()
        if row:
            row.provider_username_or_id = value
            row.confidence = "confirmed"
            row.verified_at = now
        else:
            row = EmployeeIdentity(
                tenant_id=tenant.id,
                employee_id=mapping.employee_id,
                provider=mapping.provider,
                provider_username_or_id=value,
                confidence="confirmed",
                verified_at=now,
            )
            db.add(row)

        db.query(UnmappedActivity).filter(
            UnmappedActivity.tenant_id == tenant.id,
            UnmappedActivity.provider == mapping.provider,
            UnmappedActivity.provider_user_id == value,
        ).delete(synchronize_session=False)

        db.flush()
        if row:
            saved.append(
                EmployeeIdentityRecord(
                    id=row.id,
                    employee_id=row.employee_id,
                    provider=row.provider,
                    provider_username_or_id=row.provider_username_or_id,
                )
            )

    db.commit()
    return saved
