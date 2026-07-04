import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    workspace_setup_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    employees: Mapped[list["Employee"]] = relationship(  # noqa: F821
        "Employee", back_populates="tenant"
    )
    components: Mapped[list["Component"]] = relationship(  # noqa: F821
        "Component", back_populates="tenant"
    )
    incidents: Mapped[list["IncidentRecord"]] = relationship(  # noqa: F821
        "IncidentRecord", back_populates="tenant"
    )
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User", back_populates="tenant"
    )
    memberships: Mapped[list["UserTenantMembership"]] = relationship(  # noqa: F821
        "UserTenantMembership", back_populates="tenant", cascade="all, delete-orphan"
    )
    jira_integration: Mapped["JiraIntegration | None"] = relationship(  # noqa: F821
        "JiraIntegration", back_populates="tenant", uselist=False
    )
