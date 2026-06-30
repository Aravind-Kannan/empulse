import asyncio
import json
import re
from copy import deepcopy
from datetime import UTC, datetime

from app.schemas.investigation import (
    IncidentListResponse,
    IncidentStatus,
    IncidentSummary,
    InvestigationChatRequest,
    InvestigationDiagnostics,
    InvestigationReference,
    SmeRecommendation,
)

INCIDENT_STATUSES: list[IncidentStatus] = [
    "Open",
    "Investigating",
    "Waiting for Input",
    "Resolved",
    "Closed",
]

_MOCK_INCIDENTS: list[dict] = [
    {
        "id": "inc-001",
        "title": "Payment Gateway timeout spike",
        "status": "Investigating",
        "system_scope": "Payment Gateway",
        "jira_id": "PROJ-992",
        "updated_at": "2026-06-30T10:15:00Z",
    },
    {
        "id": "inc-002",
        "title": "Auth Service elevated 503 rate",
        "status": "Open",
        "system_scope": "Auth Service",
        "jira_id": "PROJ-887",
        "updated_at": "2026-06-30T09:40:00Z",
    },
    {
        "id": "inc-003",
        "title": "Notification delivery backlog",
        "status": "Waiting for Input",
        "system_scope": "Notification Hub",
        "jira_id": "PROJ-774",
        "updated_at": "2026-06-29T18:20:00Z",
    },
    {
        "id": "inc-004",
        "title": "Checkout partial outage",
        "status": "Resolved",
        "system_scope": "Payment Gateway",
        "jira_id": "PROJ-651",
        "updated_at": "2026-06-28T14:05:00Z",
    },
    {
        "id": "inc-005",
        "title": "SSO redirect loop regression",
        "status": "Closed",
        "system_scope": "Auth Service",
        "jira_id": "PROJ-540",
        "updated_at": "2026-06-25T11:30:00Z",
    },
]

_SYSTEM_DIAGNOSTICS: dict[str, dict] = {
    "Payment Gateway": {
        "probable_root_cause": (
            "Upstream payment provider latency spike combined with exhausted "
            "connection pool on the checkout API workers."
        ),
        "confidence_score": 82.0,
        "workaround": (
            "Enable graceful degradation: route new checkouts to backup "
            "provider for 15 minutes and increase pool size to 200."
        ),
        "graph_hops": [
            "Payment Gateway",
            "ownsComponent → Ben Rivera",
            "ownsComponent → Diego Alvarez",
            "reportsTo → Alice Chen",
        ],
        "smes": [
            ("emp-eng-001", "Ben Rivera", "Engineer", 94.0, "online"),
            ("emp-eng-003", "Diego Alvarez", "Engineer", 88.0, "online"),
            ("emp-manager-001", "Alice Chen", "Manager", 72.0, "away"),
        ],
        "references": [
            ("ref-slack-1", "slack", "#payments-oncall thread", "#payments-oncall/p992", "Timeout pattern matches Feb incident"),
            ("ref-notion-1", "notion", "Payment Gateway Runbook", "notion.so/payments-runbook", "Failover steps for provider latency"),
            ("ref-pm-1", "postmortem", "PROJ-651 Postmortem", "notion.so/pm-651", "Connection pool exhaustion root cause"),
        ],
    },
    "Auth Service": {
        "probable_root_cause": (
            "Session token validation cache stampede after Redis node failover "
            "in the identity cluster."
        ),
        "confidence_score": 76.0,
        "workaround": (
            "Bypass distributed cache for token introspection for 10 minutes "
            "and scale auth pods +2 replicas."
        ),
        "graph_hops": [
            "Auth Service",
            "ownsComponent → Cara Patel",
            "reportsTo → Alice Chen",
        ],
        "smes": [
            ("emp-eng-002", "Cara Patel", "Engineer", 96.0, "online"),
            ("emp-manager-001", "Alice Chen", "Manager", 70.0, "away"),
        ],
        "references": [
            ("ref-slack-2", "slack", "#identity-team escalation", "#identity-team/p887", "Redis failover timeline"),
            ("ref-notion-2", "notion", "Auth Service Architecture", "notion.so/auth-arch", "Cache invalidation playbook"),
        ],
    },
    "Notification Hub": {
        "probable_root_cause": (
            "Webhook consumer lag due to retry storm from downstream Slack API "
            "rate limiting."
        ),
        "confidence_score": 68.0,
        "workaround": (
            "Pause non-critical notification fan-out and drain retry queue "
            "with exponential backoff cap at 30s."
        ),
        "graph_hops": [
            "Notification Hub",
            "ownsComponent → Elena Kowalski",
            "ownsComponent → Frank Osei",
        ],
        "smes": [
            ("emp-eng-004", "Elena Kowalski", "Engineer", 91.0, "online"),
            ("emp-support-001", "Frank Osei", "Support", 78.0, "offline"),
        ],
        "references": [
            ("ref-slack-3", "slack", "#comms-infra backlog", "#comms-infra/p774", "Retry queue depth chart"),
            ("ref-notion-3", "notion", "Notification Hub Playbook", "notion.so/notif-hub", "Rate limit mitigation"),
        ],
    },
}

_DEFAULT_SYSTEM = "Payment Gateway"


def list_incidents(status: IncidentStatus | None = None) -> IncidentListResponse:
    incidents = _MOCK_INCIDENTS
    if status:
        incidents = [item for item in incidents if item["status"] == status]
    return IncidentListResponse(
        incidents=[IncidentSummary(**item) for item in incidents]
    )


def update_incident_status(incident_id: str, status: IncidentStatus) -> IncidentSummary:
    for incident in _MOCK_INCIDENTS:
        if incident["id"] == incident_id:
            incident["status"] = status
            incident["updated_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            return IncidentSummary(**incident)
    raise ValueError(f"Incident '{incident_id}' not found.")


def _parse_system_scope(message: str) -> str:
    lowered = message.lower()
    for system in _SYSTEM_DIAGNOSTICS:
        if system.lower() in lowered:
            return system
    if "payment" in lowered or "checkout" in lowered:
        return "Payment Gateway"
    if "auth" in lowered or "sso" in lowered or "login" in lowered:
        return "Auth Service"
    if "notification" in lowered or "slack" in lowered or "webhook" in lowered:
        return "Notification Hub"
    return _DEFAULT_SYSTEM


def _parse_jira_id(message: str) -> str | None:
    match = re.search(r"[A-Z]+-\d+", message)
    return match.group(0) if match else None


def build_diagnostics(message: str) -> InvestigationDiagnostics:
    system = _parse_system_scope(message)
    template = deepcopy(_SYSTEM_DIAGNOSTICS[system])

    jira_id = _parse_jira_id(message)
    if jira_id:
        template["graph_hops"].append(f"linkedJira → {jira_id}")

    smes = [
        SmeRecommendation(
            employee_id=item[0],
            name=item[1],
            role=item[2],
            compatibility_score=item[3],
            status=item[4],
        )
        for item in template["smes"]
    ]
    references = [
        InvestigationReference(
            id=item[0],
            type=item[1],
            title=item[2],
            url=item[3],
            snippet=item[4],
        )
        for item in template["references"]
    ]

    return InvestigationDiagnostics(
        probable_root_cause=template["probable_root_cause"],
        confidence_score=template["confidence_score"],
        workaround=template["workaround"],
        smes=smes,
        references=references,
        graph_hops=template["graph_hops"],
    )


async def stream_investigation_chat(payload: InvestigationChatRequest):
    system = _parse_system_scope(payload.message)
    jira = _parse_jira_id(payload.message)
    intro = (
        f"Traversing Cognee knowledge graph for **{system}**"
        + (f" (Jira {jira})" if jira else "")
        + "…\n\n"
    )
    narrative = (
        f"Found {len(_SYSTEM_DIAGNOSTICS[system]['graph_hops'])} hops across "
        "ownership and reporting edges. Correlating incident history with "
        "component metadata and prior postmortems.\n\n"
        "Diagnostics synthesized from graph proximity and historical patterns."
    )

    for token in intro.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.04)

    for token in narrative.split(" "):
        chunk = {"type": "token", "content": token + " "}
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.03)

    diagnostics = build_diagnostics(payload.message)
    diag_chunk = {
        "type": "diagnostics",
        "diagnostics": diagnostics.model_dump(),
    }
    yield f"data: {json.dumps(diag_chunk)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
