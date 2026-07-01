"""Live Jira REST client for ERA telemetry (Step 05)."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.schemas.integrations import JiraConfigRequest
from app.services.jira_mapper import issue_browse_url
from app.services.jira_types import JiraIssueActivity

logger = logging.getLogger(__name__)

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "jira_issues.json"
)

JIRA_FIELDS = [
    "issuetype",
    "priority",
    "status",
    "assignee",
    "components",
    "labels",
    "project",
    "parent",
    "customfield_10016",
]


class JiraClientError(ValueError):
    """Jira API or configuration error."""


def _normalize_site_url(site_url: str) -> str:
    parsed = urlparse(site_url.strip())
    if not parsed.scheme:
        return f"https://{site_url.strip().rstrip('/')}"
    return f"{parsed.scheme}://{parsed.netloc}"


def _auth_headers(config: JiraConfigRequest) -> dict[str, str]:
    token = config.api_token.strip()
    email = (config.account_email or "").strip()
    if email and token:
        raw = base64.b64encode(f"{email}:{token}".encode()).decode()
        return {
            "Authorization": f"Basic {raw}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    if token:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    raise JiraClientError("Jira API token is required for live sync.")


def load_fixture_issues(site_url: str = "https://acme.atlassian.net") -> list[JiraIssueActivity]:
    if not FIXTURE_PATH.is_file():
        raise JiraClientError(f"Jira fixture not found: {FIXTURE_PATH}")
    payload = json.loads(FIXTURE_PATH.read_text())
    return [_issue_from_dict(item, site_url=site_url) for item in payload]


def issues_from_mock_feed(site_url: str = "https://acme.atlassian.net") -> list[JiraIssueActivity]:
    """Convert legacy MOCK_JIRA_ISSUES into typed activities."""
    from app.services.integration_feeds import MOCK_JIRA_ISSUES

    issues: list[JiraIssueActivity] = []
    for row in MOCK_JIRA_ISSUES:
        status = row.get("status", "Open")
        status_category = "done" if status.lower() == "done" else "indeterminate"
        issues.append(
            JiraIssueActivity(
                issue_key=row["ticket_id"],
                issue_type=row["issue_type"],
                priority=row["priority"],
                status=status,
                status_category=status_category,
                project_key=row["project_key"],
                assignee_provider_user_id=row.get("assignee_provider_user_id"),
                component_id=row.get("component_id"),
                issue_url=issue_browse_url(site_url, row["ticket_id"]),
            )
        )
    return issues


def _issue_from_dict(item: dict, *, site_url: str) -> JiraIssueActivity:
    key = item["issue_key"]
    return JiraIssueActivity(
        issue_key=key,
        issue_type=item["issue_type"],
        priority=item["priority"],
        status=item["status"],
        status_category=item.get("status_category", "indeterminate"),
        project_key=item["project_key"],
        assignee_provider_user_id=item.get("assignee_provider_user_id"),
        assignee_email=item.get("assignee_email"),
        component_id=item.get("component_id"),
        jira_component_names=item.get("jira_component_names", []),
        labels=item.get("labels", []),
        story_points=float(item.get("story_points", 0.0) or 0.0),
        is_subtask=bool(item.get("is_subtask", False)),
        issue_url=item.get("issue_url") or issue_browse_url(site_url, key),
    )


def _issue_from_api_payload(issue: dict, *, site_url: str) -> JiraIssueActivity:
    fields = issue.get("fields") or {}
    issue_type = (fields.get("issuetype") or {}).get("name") or "Task"
    priority = (fields.get("priority") or {}).get("name") or "Medium"
    status = (fields.get("status") or {}).get("name") or "Open"
    status_category = (
        (fields.get("status") or {}).get("statusCategory") or {}
    ).get("key") or "indeterminate"
    project_key = (fields.get("project") or {}).get("key") or ""
    assignee = fields.get("assignee")
    assignee_id = None
    assignee_email = None
    if assignee:
        assignee_id = assignee.get("accountId") or assignee.get("name")
        assignee_email = assignee.get("emailAddress")
    components = [row.get("name", "") for row in (fields.get("components") or []) if row]
    labels = list(fields.get("labels") or [])
    parent = fields.get("parent")
    story_points = fields.get("customfield_10016") or 0.0
    key = issue.get("key") or ""
    return JiraIssueActivity(
        issue_key=key,
        issue_type=issue_type,
        priority=priority,
        status=status,
        status_category=status_category,
        project_key=project_key,
        assignee_provider_user_id=assignee_id,
        assignee_email=assignee_email,
        jira_component_names=[name for name in components if name],
        labels=labels,
        story_points=float(story_points or 0.0),
        is_subtask=bool(parent),
        issue_url=issue_browse_url(site_url, key),
    )


class JiraClient:
    def __init__(self, config: JiraConfigRequest, *, use_fixture: bool = False) -> None:
        self.config = config
        self.use_fixture = use_fixture
        self.site_url = _normalize_site_url(config.site_url)
        self._session = requests.Session()

    def fetch_open_issues(self) -> list[JiraIssueActivity]:
        if self.use_fixture:
            return load_fixture_issues(self.site_url)
        if not self.config.api_token.strip():
            logger.warning("No Jira token configured; using embedded mock issue feed")
            return issues_from_mock_feed(self.site_url)

        project_keys = [
            key.strip().upper()
            for key in self.config.project_keys.split(",")
            if key.strip()
        ]
        jql_parts = ["statusCategory != Done"]
        if project_keys:
            joined = ", ".join(f'"{key}"' for key in project_keys)
            jql_parts.insert(0, f"project in ({joined})")
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        issues: list[JiraIssueActivity] = []
        next_page_token: str | None = None
        while len(issues) < 500:
            body: dict[str, object] = {
                "jql": jql,
                "fields": JIRA_FIELDS,
                "maxResults": 100,
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token
            response = self._request(
                "POST",
                "/rest/api/3/search/jql",
                json=body,
            )
            payload = response.json()
            rows = payload.get("issues") or []
            if not rows:
                break
            for row in rows:
                issues.append(_issue_from_api_payload(row, site_url=self.site_url))
            if payload.get("isLast", True):
                break
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break
        return issues

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.site_url}{path}"
        response = self._session.request(
            method,
            url,
            headers=_auth_headers(self.config),
            timeout=30,
            **kwargs,
        )
        if response.status_code == 429:
            raise JiraClientError("Jira API rate limit exceeded; retry later.")
        if response.status_code >= 400:
            raise JiraClientError(
                f"Jira API {method} {path} failed ({response.status_code}): "
                f"{response.text[:200]}"
            )
        return response


def fetch_jira_issues(
    config: JiraConfigRequest,
    *,
    use_fixture: bool = False,
) -> list[JiraIssueActivity]:
    return JiraClient(config, use_fixture=use_fixture).fetch_open_issues()
