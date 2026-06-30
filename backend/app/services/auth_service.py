"""Password hashing, user/tenant provisioning, and session helpers."""

from __future__ import annotations

import uuid

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.schemas.auth import UserResponse
from app.tenancy import slugify_company

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def _unique_tenant_slug(db: Session, company_name: str) -> str:
    base = slugify_company(company_name)
    slug = base
    suffix = 1
    while db.query(Tenant).filter(Tenant.slug == slug).one_or_none():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def create_tenant_and_user(
    db: Session,
    *,
    email: str,
    name: str,
    company_name: str,
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
        raise ValueError(
            "This email is already registered. Sign in with your password instead."
        )

    company_name = f"{name.split()[0]}'s Workspace" if name else "My Workspace"
    return create_tenant_and_user(
        db,
        email=email,
        name=name,
        company_name=company_name,
        oauth_provider=provider,
        oauth_subject=subject,
    )


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
        created_at=user.created_at,
    )
