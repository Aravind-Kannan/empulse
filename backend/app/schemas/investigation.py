from typing import Literal

from pydantic import BaseModel, Field

IncidentStatus = Literal[
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
]


class IncidentSummary(BaseModel):
    id: str
    title: str
    status: IncidentStatus
    system_scope: str
    jira_id: str
    updated_at: str


class IncidentListResponse(BaseModel):
    incidents: list[IncidentSummary]


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class SmeRecommendation(BaseModel):
    employee_id: str
    name: str
    role: str
    compatibility_score: float = Field(ge=0, le=100)
    status: Literal["online", "away", "offline"]


class InvestigationReference(BaseModel):
    id: str
    type: Literal["slack", "notion", "postmortem"]
    title: str
    url: str
    snippet: str


class InvestigationDiagnostics(BaseModel):
    probable_root_cause: str
    confidence_score: float = Field(ge=0, le=100)
    workaround: str
    smes: list[SmeRecommendation]
    references: list[InvestigationReference]
    graph_hops: list[str] = Field(default_factory=list)


class InvestigationChatRequest(BaseModel):
    message: str
    incident_id: str | None = None


class InvestigationChatChunk(BaseModel):
    type: Literal["token", "diagnostics", "done"]
    content: str | None = None
    diagnostics: InvestigationDiagnostics | None = None
