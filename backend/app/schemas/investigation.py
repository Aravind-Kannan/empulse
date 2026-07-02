from typing import Literal

from pydantic import BaseModel, Field

IncidentStatus = Literal[
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
]

IncidentSource = Literal["jira", "slack"]


class IncidentSummary(BaseModel):
    id: str
    title: str
    status: IncidentStatus
    system_scope: str
    jira_id: str = ""
    updated_at: str
    source: IncidentSource
    priority: str | None = None
    channel_name: str | None = None


class IncidentListResponse(BaseModel):
    incidents: list[IncidentSummary]
    suggestions: list[str] = Field(default_factory=list)
    sources_connected: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    resolution_note: str | None = None


class SmeRecommendation(BaseModel):
    employee_id: str
    name: str
    role: str
    compatibility_score: float = Field(ge=0, le=100)
    status: Literal["online", "away", "offline"]


class InvestigationReference(BaseModel):
    id: str
    type: Literal["slack", "notion", "postmortem", "jira"]
    title: str
    url: str
    snippet: str


class InvestigationDiagnostics(BaseModel):
    probable_root_cause: str
    confidence_score: float = Field(ge=0, le=100)
    workaround: str
    smes: list[SmeRecommendation]
    references: list[InvestigationReference]
    slack_threads: list[InvestigationReference] = Field(default_factory=list)
    jira_tickets: list[InvestigationReference] = Field(default_factory=list)
    notion_pages: list[InvestigationReference] = Field(default_factory=list)
    graph_hops: list[str] = Field(default_factory=list)


class InvestigationChatRequest(BaseModel):
    message: str
    incident_id: str | None = None


class InvestigationChatChunk(BaseModel):
    type: Literal["token", "diagnostics", "status", "done"]
    content: str | None = None
    phase: Literal["searching", "matching", "summarizing"] | None = None
    message: str | None = None
    diagnostics: InvestigationDiagnostics | None = None
