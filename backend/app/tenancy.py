"""Multi-tenant request context: PostgreSQL scoping and Cognee dataset isolation."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import DEFAULT_TENANT_ID, Tenant
from app.services.jwt_service import AUTH_COOKIE, decode_access_token

TENANT_COOKIE = "empulse_tenant_id"
TENANT_HEADER = "X-Tenant-ID"
TENANT_SLUG_HEADER = "X-Tenant-Slug"


def _tenant_id_from_verified_token(token: str) -> uuid.UUID | None:
    payload = decode_access_token(token)
    if not payload:
        return None
    claim = payload.get("tenant_id")
    if not claim:
        return None
    try:
        return uuid.UUID(str(claim))
    except ValueError:
        return None


def _parse_tenant_id(raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def ensure_default_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).one_or_none()
    if tenant:
        return tenant

    tenant = Tenant(
        id=DEFAULT_TENANT_ID,
        company_name="Acme Company",
        slug="acme",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Resolve the active tenant from (in priority order):
    1. X-Tenant-ID header
    2. empulse_tenant_id
    3. Verified JWT in empulse_auth_token cookie or Bearer header
    4. X-Tenant-Slug header (lookup by slug)
    5. Default bootstrap tenant (Acme)
    """
    tenant_id = _parse_tenant_id(request.headers.get(TENANT_HEADER))
    if not tenant_id:
        tenant_id = _parse_tenant_id(request.cookies.get(TENANT_COOKIE))

    if not tenant_id:
        auth_token = request.cookies.get(AUTH_COOKIE)
        if auth_token:
            tenant_id = _tenant_id_from_verified_token(auth_token)

    if not tenant_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            tenant_id = _tenant_id_from_verified_token(
                auth_header.removeprefix("Bearer ").strip()
            )

    if tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        return tenant

    slug = request.headers.get(TENANT_SLUG_HEADER)
    if slug:
        tenant = db.query(Tenant).filter(Tenant.slug == slug.strip().lower()).one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        return tenant

    return ensure_default_tenant(db)


CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]


def tenant_dataset_name(tenant_id: uuid.UUID) -> str:
    """Namespace-isolated Cognee dataset per tenant."""
    safe = str(tenant_id).replace("-", "")
    return f"empulse_tenant_{safe}"


def slugify_company(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"
