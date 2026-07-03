"""Shared fixtures for backend unit tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import Base
from app.models.integration_sync_job import IntegrationSyncJob  # noqa: F401
from app.models.integration_sync_record import IntegrationSyncRecord  # noqa: F401
from app.models.operational import Employee
from app.models.tenant import Tenant


@pytest.fixture(autouse=True)
def _clear_github_provider_member_cache():
    from app.services.github_identity import clear_provider_member_cache

    clear_provider_member_cache()
    yield
    clear_provider_member_cache()


@pytest.fixture()
def db() -> Session:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autocommit=False, autoflush=False)()
    Base.metadata.create_all(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-4000-8000-000000000099")


@pytest.fixture()
def tenant(db: Session, tenant_id: uuid.UUID) -> Tenant:
    row = Tenant(
        id=tenant_id,
        company_name="Test Co",
        slug="test-co-era-step01",
    )
    db.add(row)
    db.commit()
    return row


def add_employee(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    employee_id: str,
    name: str,
    email: str,
) -> Employee:
    employee = Employee(
        id=employee_id,
        tenant_id=tenant_id,
        name=name,
        role="Engineer",
        email=email,
        tenure_years=1.0,
    )
    db.add(employee)
    db.commit()
    return employee
