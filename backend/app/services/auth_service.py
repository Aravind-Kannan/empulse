"""Password hashing, user/tenant provisioning, and session helpers."""

from __future__ import annotations

import uuid

import bcrypt
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.schemas.auth import UserResponse
from app.tenancy import slugify_company

_CONSUMER_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "icloud.com",
        "me.com",
        "proton.me",
        "protonmail.com",
    }
)


def is_consumer_email(email: str) -> bool:
    domain = email.split("@")[-1].strip().lower()
    return not domain or domain in _CONSUMER_EMAIL_DOMAINS


def company_name_from_email(email: str) -> str | None:
    domain = email.split("@")[-1].strip().lower()
    if not domain or domain in _CONSUMER_EMAIL_DOMAINS:
        return None
    label = domain.split(".")[0]
    if not label:
        return None
    return label.replace("-", " ").title()


def resolve_signup_company_name(
    *,
    email: str,
    name: str,
    company_name: str | None = None,
) -> tuple[str, bool]:
    """Return workspace name and whether setup can be skipped."""
    if company_name and company_name.strip():
        return company_name.strip(), True

    inferred = company_name_from_email(email)
    if inferred:
        return inferred, True

    placeholder = (
        f"{name.split()[0]}'s Workspace"
        if name.strip()
        else "My Workspace"
    )
    return placeholder, False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def _unique_tenant_slug(
    db: Session,
    company_name: str,
    *,
    exclude_tenant_id: uuid.UUID | None = None,
) -> str:
    base = slugify_company(company_name)
    slug = base
    suffix = 1
    while True:
        existing = db.query(Tenant).filter(Tenant.slug == slug).one_or_none()
        if existing is None or (
            exclude_tenant_id is not None and existing.id == exclude_tenant_id
        ):
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def create_tenant_and_user(
    db: Session,
    *,
    email: str,
    name: str,
    company_name: str,
    workspace_setup_complete: bool = True,
    password: str | None = None,
    oauth_provider: str | None = None,
    oauth_subject: str | None = None,
) -> tuple[User, Tenant, bool]:
    existing = db.query(User).filter(User.email == email.lower()).one_or_none()
    if existing:
        raise ValueError("An account with this email already exists.")

    tenant = Tenant(
        company_name=company_name,
        slug=_unique_tenant_slug(db, company_name),
        workspace_setup_complete=workspace_setup_complete,
    )
    db.add(tenant)
    db.flush()

    user = User(
        email=email.lower(),
        name=name,
        password_hash=hash_password(password) if password else None,
        tenant_id=tenant.id,
        oauth_provider=oauth_provider,
        oauth_subject=oauth_subject,
        onboarded=False,
    )
    db.add(user)
    db.flush()
    db.add(
        UserTenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
        )
    )
    db.commit()
    db.refresh(user)
    db.refresh(tenant)
    return user, tenant, True


def authenticate_password_user(
    db: Session,
    *,
    email: str,
    password: str,
) -> User:
    user = db.query(User).filter(User.email == email.lower()).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password.")
    return user


def find_or_create_oauth_user(
    db: Session,
    *,
    email: str,
    name: str,
    provider: str,
    subject: str,
    company_name: str | None = None,
) -> tuple[User, Tenant, bool]:
    user = (
        db.query(User)
        .filter(User.oauth_provider == provider, User.oauth_subject == subject)
        .one_or_none()
    )
    if user:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).one()
        return user, tenant, False

    existing_email = db.query(User).filter(User.email == email.lower()).one_or_none()
    if existing_email:
        if existing_email.oauth_provider:
            provider_label = existing_email.oauth_provider.title()
            raise ValueError(
                f"This email is already registered. Sign in with {provider_label} instead."
            )
        raise ValueError(
            "This email is already registered. Sign in with your password instead."
        )

    resolved_company, workspace_setup_complete = resolve_signup_company_name(
        email=email,
        name=name,
        company_name=company_name,
    )
    return create_tenant_and_user(
        db,
        email=email,
        name=name,
        company_name=resolved_company,
        workspace_setup_complete=workspace_setup_complete,
        oauth_provider=provider,
        oauth_subject=subject,
    )


def update_tenant_workspace_name(
    db: Session,
    tenant: Tenant,
    company_name: str,
) -> Tenant:
    cleaned = company_name.strip()
    if not cleaned:
        raise ValueError("Workspace name is required.")

    tenant.company_name = cleaned
    tenant.slug = _unique_tenant_slug(
        db,
        cleaned,
        exclude_tenant_id=tenant.id,
    )
    tenant.workspace_setup_complete = True
    db.commit()
    db.refresh(tenant)
    return tenant


def user_to_response(user: User, tenant: Tenant) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        tenant_id=user.tenant_id,
        company_name=tenant.company_name,
        tenant_slug=tenant.slug,
        onboarded=user.onboarded,
        oauth_provider=user.oauth_provider,
        workspace_setup_complete=tenant.workspace_setup_complete,
        created_at=user.created_at,
    )
