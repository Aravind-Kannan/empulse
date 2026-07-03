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
    "unmapped_activities",
    "github_ownership_snapshots",
    "doa_file_snapshots",
    "file_risk_snapshots",
    "notion_doc_snapshots",
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

        if inspector.has_table("employee_identities"):
            identity_columns = _column_names(inspector, "employee_identities")
            if "confidence" not in identity_columns:
                logger.info("Adding confidence column to employee_identities")
                conn.execute(
                    text(
                        "ALTER TABLE employee_identities "
                        "ADD COLUMN confidence VARCHAR(16) NOT NULL DEFAULT 'confirmed'"
                    )
                )
            if "verified_at" not in identity_columns:
                logger.info("Adding verified_at column to employee_identities")
                conn.execute(
                    text(
                        "ALTER TABLE employee_identities "
                        "ADD COLUMN verified_at TIMESTAMP"
                    )
                )

        if inspector.has_table("components"):
            component_columns = _column_names(inspector, "components")
            if "criticality" not in component_columns:
                logger.info("Adding criticality column to components")
                conn.execute(
                    text(
                        "ALTER TABLE components "
                        "ADD COLUMN criticality VARCHAR(32) NOT NULL DEFAULT 'tier2_core'"
                    )
                )
            if "tags" not in component_columns:
                logger.info("Adding tags column to components")
                conn.execute(
                    text(
                        "ALTER TABLE components "
                        "ADD COLUMN tags VARCHAR(512) NOT NULL DEFAULT ''"
                    )
                )

        if inspector.has_table("employees"):
            employee_columns = _column_names(inspector, "employees")
            if "active" not in employee_columns:
                logger.info("Adding active column to employees")
                conn.execute(
                    text(
                        "ALTER TABLE employees "
                        "ADD COLUMN active BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_employees_active ON employees (active)")
                )

        if inspector.has_table("integration_sync_jobs"):
            job_columns = _column_names(inspector, "integration_sync_jobs")
            if "job_kind" not in job_columns:
                logger.info("Adding job_kind column to integration_sync_jobs")
                conn.execute(
                    text(
                        "ALTER TABLE integration_sync_jobs "
                        "ADD COLUMN job_kind VARCHAR(32) NOT NULL DEFAULT 'source'"
                    )
                )
            if "repository_url" not in job_columns:
                logger.info("Adding repository_url column to integration_sync_jobs")
                conn.execute(
                    text(
                        "ALTER TABLE integration_sync_jobs "
                        "ADD COLUMN repository_url VARCHAR(512)"
                    )
                )
            job_columns = _column_names(inspector, "integration_sync_jobs")
            if "progress_stats" not in job_columns:
                logger.info("Adding progress_stats column to integration_sync_jobs")
                conn.execute(
                    text(
                        "ALTER TABLE integration_sync_jobs "
                        "ADD COLUMN progress_stats JSON"
                    )
                )

    from app.models.operational import (
        DoaFileSnapshot,
        EraAlert,
        EraDepartureOrphanBaseline,
        EraEvidenceMitigation,
        EraRiskSnapshot,
        EraTeamHealthSnapshot,
        EraTeamReview,
        FileRiskSnapshot,
        GitHubOwnershipSnapshot,
        NotionDocSnapshot,
        TenantIntegrationConfig,
        UnmappedActivity,
    )

    UnmappedActivity.__table__.create(bind=engine, checkfirst=True)
    GitHubOwnershipSnapshot.__table__.create(bind=engine, checkfirst=True)
    DoaFileSnapshot.__table__.create(bind=engine, checkfirst=True)
    FileRiskSnapshot.__table__.create(bind=engine, checkfirst=True)
    NotionDocSnapshot.__table__.create(bind=engine, checkfirst=True)
    EraRiskSnapshot.__table__.create(bind=engine, checkfirst=True)
    EraEvidenceMitigation.__table__.create(bind=engine, checkfirst=True)
    EraAlert.__table__.create(bind=engine, checkfirst=True)
    EraTeamReview.__table__.create(bind=engine, checkfirst=True)
    EraTeamHealthSnapshot.__table__.create(bind=engine, checkfirst=True)
    EraDepartureOrphanBaseline.__table__.create(bind=engine, checkfirst=True)
    TenantIntegrationConfig.__table__.create(bind=engine, checkfirst=True)
