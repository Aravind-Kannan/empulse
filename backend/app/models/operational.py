import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_employees_tenant_email"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    tenure_years: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    manager_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    team_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="employees")
    manager: Mapped["Employee | None"] = relationship(
        "Employee", remote_side="Employee.id", back_populates="direct_reports"
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        "Employee", back_populates="manager"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="employee", cascade="all, delete-orphan"
    )
    identities: Mapped[list["EmployeeIdentity"]] = relationship(
        "EmployeeIdentity", back_populates="employee", cascade="all, delete-orphan"
    )
    role_history: Mapped[list["RoleHistory"]] = relationship(
        "RoleHistory", back_populates="employee", cascade="all, delete-orphan"
    )


class RoleHistory(Base):
    __tablename__ = "role_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False
    )
    old_role: Mapped[str] = mapped_column(String(128), nullable=False)
    new_role: Mapped[str] = mapped_column(String(128), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="role_history")


class EmployeeIdentity(Base):
    __tablename__ = "employee_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_username_or_id: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="identities")


class UnmappedActivity(Base):
    __tablename__ = "unmapped_activities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_user_id",
            "event_type",
            name="uq_unmapped_activity_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class Component(Base):
    __tablename__ = "components"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    open_tasks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unresolved_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criticality: Mapped[str] = mapped_column(
        String(32), nullable=False, default="tier2_core"
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="components")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment", back_populates="component", cascade="all, delete-orphan"
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False
    )
    codebase_share_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="assignments")
    component: Mapped["Component"] = relationship("Component", back_populates="assignments")


class GitHubOwnershipSnapshot(Base):
    __tablename__ = "github_ownership_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "component_id",
            "employee_id",
            name="uq_github_ownership_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False
    )
    ownership_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class DoaFileSnapshot(Base):
    __tablename__ = "doa_file_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "component_id",
            "file_path",
            "employee_id",
            name="uq_doa_file_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False, index=True
    )
    doa_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_author: Mapped[bool] = mapped_column(nullable=False, default=False)
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decay_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class FileRiskSnapshot(Base):
    __tablename__ = "file_risk_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "component_id",
            "file_path",
            name="uq_file_risk_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False, index=True
    )
    repo_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    churn_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contributor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bus_factor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quadrant: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    primary_owner_employee_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    primary_owner_doa_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class NotionDocSnapshot(Base):
    __tablename__ = "notion_doc_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "page_id",
            name="uq_notion_doc_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    page_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    page_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    component_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=True, index=True
    )
    owner_employee_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    page_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="runbook")
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expertise_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class EraEvidenceMitigation(Base):
    __tablename__ = "era_evidence_mitigations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "evidence_id",
            name="uq_era_evidence_mitigation",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mitigation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    suggested_mitigation: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mitigation_assignee_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    mitigation_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    mitigation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EraRiskSnapshot(Base):
    __tablename__ = "era_risk_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "snapshot_date",
            name="uq_era_risk_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    risk_factor_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low")
    dimensions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class EraAlert(Base):
    __tablename__ = "era_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    employee_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=True
    )
    component_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=True
    )
    evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webhook_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EraTeamHealthSnapshot(Base):
    __tablename__ = "era_team_health_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "snapshot_date",
            name="uq_era_team_health_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    org_health_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    orphan_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    orphan_delta_90d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class EraDepartureOrphanBaseline(Base):
    __tablename__ = "era_departure_orphan_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("employees.id"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("components.id"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    doa_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    snapshotted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )


class EraTeamReview(Base):
    __tablename__ = "era_team_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_avg_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delta_since_last: Mapped[float | None] = mapped_column(Float, nullable=True)


class TenantIntegrationConfig(Base):
    __tablename__ = "tenant_integration_configs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            name="uq_tenant_integration_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class IncidentRecord(Base):
    __tablename__ = "incident_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    system_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    jira_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="incidents")
