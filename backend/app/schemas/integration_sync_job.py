import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.integrations import IntegrationSyncResponse

IntegrationSyncJobStatus = Literal["queued", "running", "completed", "failed"]
IntegrationSyncPhase = Literal["fetching", "building_graph", "cognifying", "finalizing"]


class IntegrationSyncJobAcceptedResponse(BaseModel):
    job_id: uuid.UUID
    source: str
    status: IntegrationSyncJobStatus
    poll_url: str
    message: str


class IntegrationSyncJobsAcceptedResponse(BaseModel):
    jobs: list[IntegrationSyncJobAcceptedResponse]
    message: str


class IntegrationSyncJobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    source: str
    status: IntegrationSyncJobStatus
    phase: IntegrationSyncPhase | None = None
    progress_message: str | None = None
    error: str | None = None
    result: IntegrationSyncResponse | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class IntegrationSyncJobListResponse(BaseModel):
    jobs: list[IntegrationSyncJobStatusResponse] = Field(default_factory=list)
