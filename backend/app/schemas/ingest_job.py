import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.org import OrgChartIngestResponse

IngestJobStatus = Literal["queued", "running", "completed", "failed"]


class IngestJobAcceptedResponse(BaseModel):
    job_id: uuid.UUID
    status: IngestJobStatus
    poll_url: str
    message: str


class IngestJobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: IngestJobStatus
    job_type: str
    company: str
    employees_persisted: int
    components_persisted: int
    assignments_persisted: int
    error: str | None = None
    result: OrgChartIngestResponse | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
