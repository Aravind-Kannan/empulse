import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    slug: str
    created_at: datetime


class WorkspaceWipeResponse(BaseModel):
    tenant_id: str
    counts: dict[str, int] = Field(default_factory=dict)
    total_rows_removed: int = 0
    message: str
