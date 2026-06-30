from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.org import OrgChartIngestRequest, OrgChartIngestResponse


class BulkCsvRow(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    email: EmailStr
    dynamic_role: str = Field(min_length=1)
    team_name: str | None = None
    reports_to_email_or_id: str | None = None


class BulkUploadRequest(BaseModel):
    company: str = "Acme Company"
    rows: list[BulkCsvRow]
    current_org: OrgChartIngestRequest | None = None
    dry_run: bool = True


class BulkDiffEntry(BaseModel):
    kind: Literal["added", "removed", "modified"]
    employee_id: str
    name: str
    changes: list[str] = Field(default_factory=list)


class BulkUploadResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    diff: list[BulkDiffEntry] = Field(default_factory=list)
    merged_org: OrgChartIngestRequest | None = None
    sync_result: OrgChartIngestResponse | None = None
