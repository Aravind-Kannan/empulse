"""Tracks integration items already ingested into Cognee (incremental sync ledger)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IntegrationSyncRecord(Base):
    __tablename__ = "integration_sync_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "source",
            "external_key",
            name="uq_integration_sync_record",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_version: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    display_label: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
