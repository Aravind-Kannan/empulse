"""Live Jira REST client for ERA telemetry (Step 05)."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import ReadTimeout, RequestException

from app.schemas.identity import ProviderMember
from app.schemas.integrations import JiraConfigRequest
from app.services.jira_mapper import issue_browse_url
from app.services.jira_text import adf_to_plain_text, truncate_jira_text
from app.services.jira_types import JiraIssueActivity
from app.services.jira_user_email import enrich_jira_users_with_emails

logger = logging.getLogger(__name__)

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "jira_issues.json"
)

JIRA_FIELDS = [
    "summary",
    "description",
    "updated",
    "issuetype",
    "priority",
    "status",
    "assignee",
    "reporter",
    "components",
    "labels",
    "project",
    "parent",
    "resolution",
    "issuelinks",
    "customfield_10016",
]

JIRA_COMMENT_FETCH_LIMIT = 5

# (connect_timeout_seconds, read_timeout_seconds)
JIRA_REQUEST_TIMEOUT = (10, 90)
JIRA_REQUEST_RETRIES = 3

JIRA_PERSON_ACCOUNT_TYPES = {"atlassian", "customer"}
JIRA_APP_ACCOUNT_TYPES = {"app"}

FIXTURE_PROJECT_COMPONENTS: dict[str, list[str]] = {
    "ENG": ["Authentication", "Payments", "Notifications"],
    "OPS": ["Platform Operations"],
    "PLAT": ["Platform Core"],
}


@dataclass(frozen=True)
class JiraProjectComponent:
    project_key: str
    name: str
    jira_id: str = ""


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
        lowered = status.lower()
        status_category = (
            "done"
            if lowered in {"done", "closed", "resolved", "complete"}
            else "indeterminate"
        )
        issues.append(
            JiraIssueActivity(
                issue_key=row["ticket_id"],
                issue_type=row["issue_type"],
                priority=row["priority"],
                status=status,
                status_category=status_category,
                project_key=row["project_key"],
                summary=row.get("description", row["ticket_id"])[:200],
                assignee_provider_user_id=row.get("assignee_provider_user_id"),
                component_id=row.get("component_id"),
                issue_url=issue_browse_url(site_url, row["ticket_id"]),
            )
        )
    return issues


def _parse_person_ref(person: dict | None) -> tuple[str | None, str | None]:
    if not person:
        return None, None
    user_id = person.get("accountId") or person.get("name")
    email = person.get("emailAddress")
    return (str(user_id) if user_id else None, email)


def _parse_linked_issue_keys(fields: dict) -> list[str]:
    linked: list[str] = []
    for link in fields.get("issuelinks") or []:
        if not isinstance(link, dict):
            continue
        for side in ("inwardIssue", "outwardIssue"):
            issue = link.get(side) or {}
            key = issue.get("key")
            if key and key not in linked:
                linked.append(str(key))
    return linked


def _issue_from_dict(item: dict, *, site_url: str) -> JiraIssueActivity:
    key = item["issue_key"]
    updated_raw = item.get("updated_at")
    updated_at = None
    if updated_raw:
        try:
            updated_at = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    return JiraIssueActivity(
        issue_key=key,
        issue_type=item["issue_type"],
        priority=item["priority"],
        status=item["status"],
        status_category=item.get("status_category", "indeterminate"),
        project_key=item["project_key"],
        summary=item.get("summary", key),
        updated_at=updated_at,
        assignee_provider_user_id=item.get("assignee_provider_user_id"),
        assignee_email=item.get("assignee_email"),
        component_id=item.get("component_id"),
        jira_component_names=item.get("jira_component_names", []),
        labels=item.get("labels", []),
        story_points=float(item.get("story_points", 0.0) or 0.0),
        is_subtask=bool(item.get("is_subtask", False)),
        issue_url=item.get("issue_url") or issue_browse_url(site_url, key),
        description_text=truncate_jira_text(str(item.get("description_text") or "")),
        resolution=str(item.get("resolution") or ""),
        reporter_provider_user_id=item.get("reporter_provider_user_id"),
        reporter_email=item.get("reporter_email"),
        linked_issue_keys=list(item.get("linked_issue_keys") or []),
        recent_comments=[
            truncate_jira_text(str(comment), max_len=400)
            for comment in (item.get("recent_comments") or [])
            if str(comment).strip()
        ],
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
    assignee_id, assignee_email = _parse_person_ref(fields.get("assignee"))
    reporter_id, reporter_email = _parse_person_ref(fields.get("reporter"))
    components = [row.get("name", "") for row in (fields.get("components") or []) if row]
    labels = list(fields.get("labels") or [])
    parent = fields.get("parent")
    story_points = fields.get("customfield_10016") or 0.0
    resolution = ((fields.get("resolution") or {}).get("name") or "").strip()
    description_text = truncate_jira_text(
        adf_to_plain_text(fields.get("description")),
    )
    linked_issue_keys = _parse_linked_issue_keys(fields)
    key = issue.get("key") or ""
    updated_raw = fields.get("updated")
    updated_at = None
    if updated_raw:
        try:
            updated_at = datetime.fromisoformat(str(updated_raw).replace("Z", "+00:00"))
        except ValueError:
            updated_at = None
    return JiraIssueActivity(
        issue_key=key,
        issue_type=issue_type,
        priority=priority,
        status=status,
        status_category=status_category,
        project_key=project_key,
        summary=(fields.get("summary") or key).strip(),
        updated_at=updated_at,
        assignee_provider_user_id=assignee_id,
        assignee_email=assignee_email,
        jira_component_names=[name for name in components if name],
        labels=labels,
        story_points=float(story_points or 0.0),
        is_subtask=bool(parent),
        issue_url=issue_browse_url(site_url, key),
        description_text=description_text,
        resolution=resolution,
        reporter_provider_user_id=reporter_id,
        reporter_email=reporter_email,
        linked_issue_keys=linked_issue_keys,
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
            logger.warning("No Jira token configured; skipping Jira issue fetch")
            return []

        project_keys = [
            key.strip().upper()
            for key in self.config.project_keys.split(",")
            if key.strip()
        ]
        jql_parts = [
            "issuetype in (Bug, Incident)",
            "statusCategory != Done",
            "updated >= -14d",
        ]
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
                "maxResults": 50,
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
        self._enrich_issue_comments(issues)
        return issues

    def _enrich_issue_comments(self, issues: list[JiraIssueActivity]) -> None:
        if self.use_fixture or not self.config.api_token.strip():
            return
        for issue in issues:
            if not issue.issue_key:
                continue
            try:
                response = self._request(
                    "GET",
                    f"/rest/api/3/issue/{issue.issue_key}/comment",
                    params={
                        "maxResults": JIRA_COMMENT_FETCH_LIMIT,
                        "orderBy": "-created",
                    },
                )
                payload = response.json()
            except (JiraClientError, RequestException) as exc:
                logger.debug(
                    "Jira comment fetch skipped for %s: %s",
                    issue.issue_key,
                    exc,
                )
                continue

            comments: list[str] = []
            for row in payload.get("comments") or []:
                body = adf_to_plain_text(row.get("body"))
                cleaned = truncate_jira_text(body, max_len=400)
                if cleaned:
                    comments.append(cleaned)
            issue.recent_comments = comments[:JIRA_COMMENT_FETCH_LIMIT]

    def fetch_incident_issues(self) -> list[JiraIssueActivity]:
        """Bugs/incidents updated recently, including Done (for investigation cards)."""
        if self.use_fixture:
            return [
                issue
                for issue in load_fixture_issues(self.site_url)
                if issue.is_bug_or_incident
            ]
        if not self.config.api_token.strip():
            logger.warning("No Jira token configured; using embedded mock issue feed")
            return [
                issue
                for issue in issues_from_mock_feed(self.site_url)
                if issue.is_bug_or_incident
            ]

        project_keys = [
            key.strip().upper()
            for key in self.config.project_keys.split(",")
            if key.strip()
        ]
        jql_parts = [
            "issuetype in (Bug, Incident)",
            "updated >= -14d",
        ]
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
                "maxResults": 50,
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
        self._enrich_issue_comments(issues)
        return issues

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.site_url}{path}"
        last_error: Exception | None = None
        for attempt in range(JIRA_REQUEST_RETRIES):
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=_auth_headers(self.config),
                    timeout=JIRA_REQUEST_TIMEOUT,
                    **kwargs,
                )
            except ReadTimeout as exc:
                last_error = exc
                if attempt + 1 >= JIRA_REQUEST_RETRIES:
                    raise JiraClientError(
                        f"Jira API timed out after {JIRA_REQUEST_TIMEOUT[1]}s "
                        f"({JIRA_REQUEST_RETRIES} attempts). Check site reachability "
                        f"and project scope, then retry."
                    ) from exc
                time.sleep(2**attempt)
                continue
            except RequestException as exc:
                raise JiraClientError(f"Jira API request failed: {exc}") from exc

            if response.status_code == 429:
                if attempt + 1 >= JIRA_REQUEST_RETRIES:
                    raise JiraClientError("Jira API rate limit exceeded; retry later.")
                retry_after = int(response.headers.get("Retry-After", "2"))
                time.sleep(max(retry_after, 2**attempt))
                continue
            if response.status_code >= 400:
                raise JiraClientError(
                    f"Jira API {method} {path} failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
            return response

        raise JiraClientError(
            f"Jira API request failed after {JIRA_REQUEST_RETRIES} attempts: {last_error}"
        )


def _is_jira_person(user: dict) -> bool:
    account_type = (user.get("accountType") or "atlassian").lower()
    if account_type in JIRA_APP_ACCOUNT_TYPES:
        return False
    if account_type not in JIRA_PERSON_ACCOUNT_TYPES:
        return False
    if user.get("active") is False:
        return False
    name = (user.get("displayName") or user.get("name") or "").strip()
    return bool(name)


def _jira_search_issues(
    site_url: str,
    headers: dict[str, str],
    jql: str,
    *,
    fields: list[str] | None = None,
    max_issues: int = 100,
) -> list[dict]:
    issue_fields = fields or ["assignee", "reporter"]
    issues: list[dict] = []
    next_page_token: str | None = None

    while len(issues) < max_issues:
        payload: dict[str, object] = {
            "jql": jql,
            "maxResults": min(50, max_issues - len(issues)),
            "fields": issue_fields,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        response = requests.post(
            f"{site_url}/rest/api/3/search/jql",
            json=payload,
            headers={**headers, "Content-Type": "application/json"},
            timeout=25,
        )
        if response.status_code >= 400:
            break

        body = response.json()
        batch = body.get("issues", [])
        if not isinstance(batch, list) or not batch:
            break
        issues.extend(batch)
        next_page_token = body.get("nextPageToken")
        if not next_page_token:
            break

    if issues:
        return issues

    legacy = requests.get(
        f"{site_url}/rest/api/3/search",
        headers=headers,
        params={
            "jql": jql,
            "maxResults": max_issues,
            "fields": ",".join(issue_fields),
        },
        timeout=25,
    )
    if legacy.status_code < 400:
        return legacy.json().get("issues", [])
    return []


def _fetch_jira_issue_people(
    site_url: str,
    headers: dict[str, str],
    project_keys: list[str],
) -> list[dict]:
    if project_keys:
        quoted = ", ".join(project_keys)
        jql = (
            f"project in ({quoted}) AND "
            "(assignee IS NOT EMPTY OR reporter IS NOT EMPTY) "
            "ORDER BY updated DESC"
        )
    else:
        jql = (
            "(assignee IS NOT EMPTY OR reporter IS NOT EMPTY) "
            "ORDER BY updated DESC"
        )

    issues = _jira_search_issues(site_url, headers, jql)
    people: dict[str, dict] = {}
    for issue in issues:
        fields = issue.get("fields") or {}
        for field_name in ("assignee", "reporter"):
            person = fields.get(field_name)
            if not person or not _is_jira_person(person):
                continue
            account_id = person.get("accountId")
            if account_id and account_id not in people:
                people[account_id] = person
    return list(people.values())


def _fetch_jira_assignable_humans(
    site_url: str,
    headers: dict[str, str],
    project_keys: list[str],
) -> list[dict]:
    people: dict[str, dict] = {}
    for key in project_keys:
        response = requests.get(
            f"{site_url}/rest/api/3/user/assignable/multiProjectSearch",
            headers=headers,
            params={"projectKeys": key, "maxResults": 100},
            timeout=20,
        )
        if response.status_code >= 400:
            continue
        for user in response.json() or []:
            if isinstance(user, dict) and _is_jira_person(user):
                account_id = user.get("accountId")
                if account_id:
                    people[account_id] = user
    return list(people.values())


def fetch_jira_provider_members(config: JiraConfigRequest) -> list[ProviderMember]:
    """List Jira users for identity mapping (accountId is the canonical provider id)."""
    if not config.api_token.strip():
        raise JiraClientError("Jira API token is required to list users.")

    site_url = _normalize_site_url(config.site_url)
    headers = _auth_headers(config)
    auth = None
    account_email = (config.account_email or "").strip()
    if account_email:
        auth = (account_email, config.api_token.strip())

    users_by_id: dict[str, dict] = {}

    def _stage_user(user: dict) -> None:
        if not _is_jira_person(user):
            return
        account_id = (user.get("accountId") or user.get("name") or "").strip()
        if account_id:
            users_by_id[account_id] = user

    project_keys = [
        key.strip().upper()
        for key in config.project_keys.split(",")
        if key.strip()
    ]

    for person in _fetch_jira_issue_people(site_url, headers, project_keys):
        _stage_user(person)

    if not users_by_id and project_keys:
        for person in _fetch_jira_assignable_humans(site_url, headers, project_keys):
            _stage_user(person)

    if not users_by_id:
        for query in ("a", "e", "i", "o", "s"):
            response = requests.get(
                f"{site_url}/rest/api/3/user/search",
                headers=headers,
                params={"query": query, "maxResults": 50},
                timeout=30,
            )
            if response.status_code >= 400:
                break
            for user in response.json() or []:
                if isinstance(user, dict):
                    _stage_user(user)

    if not users_by_id:
        logger.warning(
            "No Jira users returned for %s (projects=%s). "
            "Check API token, account email, and project keys.",
            site_url,
            ",".join(project_keys) or "none",
        )
        return []

    auth_account_id: str | None = None
    auth_user_email = account_email or None
    try:
        myself = requests.get(
            f"{site_url}/rest/api/3/myself",
            headers=headers,
            auth=auth,
            timeout=15,
        )
        if myself.status_code == 200:
            payload = myself.json()
            auth_account_id = (payload.get("accountId") or "").strip() or None
            auth_user_email = (
                (payload.get("emailAddress") or account_email or "").strip() or None
            )
    except requests.RequestException:
        pass

    email_by_account = enrich_jira_users_with_emails(
        site_url,
        list(users_by_id.values()),
        auth=auth,
        headers=headers,
        auth_user_account_id=auth_account_id,
        auth_user_email=auth_user_email,
    )

    members_by_id: dict[str, ProviderMember] = {}
    for account_id, user in users_by_id.items():
        display = (user.get("displayName") or user.get("name") or account_id).strip()
        email = email_by_account.get(account_id)
        label = display
        if email and email.lower() not in label.lower():
            label = f"{display} ({email})"
        members_by_id[account_id] = ProviderMember(
            id=account_id,
            label=label,
            email=email,
        )

    return sorted(members_by_id.values(), key=lambda member: member.label.lower())


def fetch_jira_project_components(
    config: JiraConfigRequest,
    *,
    use_fixture: bool = False,
) -> list[JiraProjectComponent]:
    """List Jira components for configured projects (REST + issue fallback)."""
    project_keys = [
        key.strip().upper()
        for key in (config.project_keys or "").split(",")
        if key.strip()
    ]
    if not project_keys:
        return []

    if use_fixture or not (config.api_token or "").strip():
        rows: list[JiraProjectComponent] = []
        for project_key in project_keys:
            for index, name in enumerate(
                FIXTURE_PROJECT_COMPONENTS.get(project_key, []),
                start=1,
            ):
                rows.append(
                    JiraProjectComponent(
                        project_key=project_key,
                        name=name,
                        jira_id=f"fixture-{project_key.lower()}-{index}",
                    )
                )
        return rows

    site_url = _normalize_site_url(config.site_url)
    headers = _auth_headers(config)
    session = requests.Session()
    discovered: list[JiraProjectComponent] = []
    seen: set[tuple[str, str]] = set()

    for project_key in project_keys:
        try:
            response = session.get(
                f"{site_url}/rest/api/3/project/{project_key}/components",
                headers=headers,
                timeout=JIRA_REQUEST_TIMEOUT,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Jira components API failed for %s (%s)",
                    project_key,
                    response.status_code,
                )
                continue
            for row in response.json() or []:
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                key = (project_key, name)
                if key in seen:
                    continue
                seen.add(key)
                discovered.append(
                    JiraProjectComponent(
                        project_key=project_key,
                        name=name,
                        jira_id=str(row.get("id") or ""),
                    )
                )
        except RequestException:
            logger.warning(
                "Jira components API request failed for %s",
                project_key,
                exc_info=True,
            )

    if discovered:
        return discovered

    for issue in JiraClient(config, use_fixture=False).fetch_open_issues():
        project_key = (issue.project_key or "").upper()
        if project_key not in project_keys:
            continue
        for name in issue.jira_component_names:
            cleaned = name.strip()
            if not cleaned:
                continue
            key = (project_key, cleaned)
            if key in seen:
                continue
            seen.add(key)
            discovered.append(
                JiraProjectComponent(
                    project_key=project_key,
                    name=cleaned,
                    jira_id="",
                )
            )
    return discovered


def fetch_jira_issues(
    config: JiraConfigRequest,
    *,
    use_fixture: bool = False,
) -> list[JiraIssueActivity]:
    return JiraClient(config, use_fixture=use_fixture).fetch_open_issues()


def fetch_jira_incident_issues(
    config: JiraConfigRequest,
    *,
    use_fixture: bool = False,
) -> list[JiraIssueActivity]:
    return JiraClient(config, use_fixture=use_fixture).fetch_incident_issues()
