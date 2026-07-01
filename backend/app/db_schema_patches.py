"""Incremental schema patches for databases created before multi-tenancy."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.models.tenant import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)

TENANT_SCOPED_TABLES = (
    "employees",
    "components",
    "assignments",
    "role_history",
    "employee_identities",
)


def _column_names(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _unique_constraint_names(inspector, table: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("name")
    }


def _drop_legacy_employees_email_unique(conn, inspector) -> None:
    """Remove pre-multi-tenant UNIQUE(email) so the same person can exist in multiple orgs."""
    if not inspector.has_table("employees"):
        return

    for constraint in inspector.get_unique_constraints("employees"):
        name = constraint.get("name")
        columns = constraint.get("column_names") or []
        if not name:
            continue
        if set(columns) == {"email"}:
            logger.info("Dropping legacy employees email unique constraint %s", name)
            conn.execute(text(f'ALTER TABLE employees DROP CONSTRAINT "{name}"'))


def apply_schema_patches(engine: Engine) -> None:
    """
    Add tenant_id to operational tables that pre-date multi-tenancy.

    SQLAlchemy create_all() does not alter existing tables; this keeps local
    PostgreSQL instances in sync with the current models.
    """
    inspector = inspect(engine)
    if not inspector.has_table("tenants"):
        return

    default_tenant = str(DEFAULT_TENANT_ID)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, company_name, slug, created_at)
                VALUES (:id, 'Acme Company', 'acme', NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": default_tenant},
        )

        for table in TENANT_SCOPED_TABLES:
            if not inspector.has_table(table):
                continue
            if "tenant_id" in _column_names(inspector, table):
                continue

            logger.info("Adding tenant_id column to %s", table)
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN tenant_id UUID"))
            conn.execute(
                text(f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id IS NULL"),
                {"tid": default_tenant},
            )
            conn.execute(
                text(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL")
            )
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_tenant_id "
                    "FOREIGN KEY (tenant_id) REFERENCES tenants(id)"
                )
            )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
                    f"ON {table} (tenant_id)"
                )
            )

        if inspector.has_table("employees"):
            _drop_legacy_employees_email_unique(conn, inspector)
            if "uq_employees_tenant_email" not in _unique_constraint_names(
                inspector, "employees"
            ):
                if "tenant_id" in _column_names(inspector, "employees"):
                    logger.info("Adding uq_employees_tenant_email constraint")
                    conn.execute(
                        text(
                            "ALTER TABLE employees "
                            "ADD CONSTRAINT uq_employees_tenant_email "
                            "UNIQUE (tenant_id, email)"
                        )
                    )
