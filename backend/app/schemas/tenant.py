import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenantSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    slug: str
    created_at: datetime
