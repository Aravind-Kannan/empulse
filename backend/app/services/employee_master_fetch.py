from __future__ import annotations

import re
import uuid
from collections import defaultdict
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from app.services.notion_client import fetch_notion_member_records
from app.schemas.employee_master import (
    EmployeeMasterDataResponse,
    FetchUsersRequest,
    MasterDataEmployee,
    MasterDataRecord,
)
from app.services.employee_ids import employee_id_from_email
from app.services.integration_sync import get_github_config, get_jira_config


def enrich_jira_credentials_from_db(
    credentials: FetchUsersRequest,
    db: Session,
    tenant_id: uuid.UUID,
) -> FetchUsersRequest:
    """Fill missing Jira fields from the tenant's saved PostgreSQL integration."""
    if "jira" not in credentials.sources:
        return credentials

    from app.services.credential_crypto import decrypt_secret
    from app.services.jira_service import get_jira_integration

    integration = get_jira_integration(db, tenant_id)
    if not integration:
        return credentials

    updates: dict[str, str] = {}
    if not (credentials.jira_site_url or "").strip():
        updates["jira_site_url"] = integration.jira_domain
    if not (credentials.jira_auth_email or "").strip():
        updates["jira_auth_email"] = integration.auth_email
    if not (credentials.jira_api_token or "").strip():
        updates["jira_api_token"] = decrypt_secret(integration.encrypted_api_token)
    if not (credentials.jira_project_keys or "").strip() and integration.project_keys:
        updates["jira_project_keys"] = integration.project_keys

    if updates:
        return credentials.model_copy(update=updates)
    return credentials


SOURCE_PRIORITY = ("notion", "slack", "jira", "github")
MANAGER_FIELD_HINTS = ("manager", "reports to", "reporting", "reports_to", "lead")


def _slug_id(email: str, tenant_id: uuid.UUID | None = None) -> str:
    if tenant_id is not None:
        return employee_id_from_email(email, tenant_id)
    local = email.split("@")[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", local).strip("-")
    return f"emp-{slug}"


def _parse_github_org(repository_url: str) -> str | None:
    parsed = urlparse(repository_url.strip())
    path = parsed.path.strip("/")
    if not path:
        return None
    return path.split("/")[0]


def _normalize_manager_ref(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    return str(value).strip()


def _extract_slack_manager_ref(profile: dict) -> str | None:
    """Resolve manager from Slack profile (Enterprise manager ID or custom fields)."""
    native = profile.get("manager")
    if native:
        return _normalize_manager_ref(str(native))

    fields = profile.get("fields") or {}
    if isinstance(fields, dict):
        for key, field in fields.items():
            if not isinstance(field, dict):
                continue
            label = f"{field.get('label', '')} {key}".lower()
            if any(hint in label for hint in MANAGER_FIELD_HINTS):
                value = field.get("value") or field.get("alt") or ""
                resolved = _normalize_manager_ref(str(value))
                if resolved:
                    return resolved
    return None


def _resolve_manager_email(
    manager_ref: str | None,
    *,
    slack_id_to_email: dict[str, str] | None = None,
    email_lookup: dict[str, str] | None = None,
) -> str | None:
    if not manager_ref:
        return None
    ref = manager_ref.strip()
    if "@" in ref:
        return ref.lower()
    if slack_id_to_email and ref in slack_id_to_email:
        return slack_id_to_email[ref].lower()
    if email_lookup and ref.lower() in email_lookup:
        return email_lookup[ref.lower()]
    return None


def _format_slack_api_error(error: str) -> str:
    if error == "missing_scope":
        return (
            "Slack bot token is missing required scopes. Add users:read and "
            "users:read.email under OAuth & Permissions, reinstall the app to "
            "your workspace, and copy a fresh xoxb- token."
        )
    if error == "invalid_auth":
        return (
            "Slack rejected this token (invalid_auth). Reinstall the app to your "
            "workspace and copy a fresh Bot User OAuth Token (xoxb-…)."
        )
    if error == "token_revoked":
        return (
            "Slack token was revoked. Reinstall the app and copy a fresh xoxb- token."
        )
    return f"Slack users.list failed: {error}"


def _fetch_slack_users_live(token: str) -> list[MasterDataRecord]:
    headers = {"Authorization": f"Bearer {token.strip()}"}
    members: list[dict] = []
    cursor: str | None = None

    while True:
        params: dict[str, str] = {"limit": "200"}
        if cursor:
            params["cursor"] = cursor
        response = requests.get(
            "https://slack.com/api/users.list",
            headers=headers,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise ValueError(
                _format_slack_api_error(payload.get("error", "unknown_error"))
            )

        members.extend(payload.get("members", []))
        cursor = (payload.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    slack_id_to_email: dict[str, str] = {}
    pending: list[tuple[dict, dict, str, str | None]] = []

    for member in members:
        if member.get("deleted") or member.get("is_bot"):
            continue
        profile = member.get("profile") or {}
        email = profile.get("email")
        if not email:
            continue
        member_id = str(member.get("id", ""))
        slack_id_to_email[member_id] = str(email).lower()
        pending.append(
            (
                member,
                profile,
                str(email).lower(),
                _extract_slack_manager_ref(profile),
            )
        )

    records: list[MasterDataRecord] = []
    for member, profile, email, manager_ref in pending:
        manager_email = _resolve_manager_email(
            manager_ref,
            slack_id_to_email=slack_id_to_email,
        )
        records.append(
            MasterDataRecord(
                source="slack",
                external_id=str(member.get("id", "")),
                name=profile.get("real_name")
                or profile.get("display_name")
                or member.get("name", "Slack User"),
                email=email,
                title=(profile.get("title") or "").strip() or "Team Member",
                manager_email=manager_email,
            )
        )

    if not records:
        human_members = [
            member
            for member in members
            if not member.get("deleted") and not member.get("is_bot")
        ]
        if human_members:
            raise ValueError(
                "Slack returned workspace members but none have email addresses. "
                "Add the users:read.email bot scope under OAuth & Permissions, "
                "reinstall the app to your workspace, and try again."
            )
        raise ValueError("Slack returned no importable workspace members.")

    return records


def _fetch_github_org_members_live(
    repository_url: str,
    token: str,
) -> list[MasterDataRecord]:
    org = _parse_github_org(repository_url)
    if not org:
        raise ValueError("GitHub repository URL must include an org or owner segment.")

    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    records: list[MasterDataRecord] = []
    page = 1
    while True:
        response = requests.get(
            f"https://api.github.com/orgs/{org}/members",
            headers=headers,
            params={"per_page": 100, "page": page},
            timeout=20,
        )
        if response.status_code == 404:
            return _fetch_github_users_fallback(org)
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break

        for member in batch:
            login = member.get("login", "github-user")
            user_resp = requests.get(
                member.get("url", f"https://api.github.com/users/{login}"),
                headers=headers,
                timeout=15,
            )
            profile = user_resp.json() if user_resp.ok else {}
            email = profile.get("email") or f"{login}@users.noreply.github.com"
            records.append(
                MasterDataRecord(
                    source="github",
                    external_id=str(member.get("id", login)),
                    name=profile.get("name") or login,
                    email=email,
                    title="GitHub Org Member",
                    manager_email=None,
                )
            )
        if len(batch) < 100:
            break
        page += 1

    return records or _fetch_github_users_fallback(org)


def _fetch_github_users_fallback(org: str) -> list[MasterDataRecord]:
    return [
        MasterDataRecord(
            source="github",
            external_id=f"gh-{org}-owner",
            name=f"{org} Owner",
            email=f"{org}@users.noreply.github.com",
            title="Repository Owner",
            manager_email=None,
        ),
    ]


def _fetch_slack_users_fallback() -> list[MasterDataRecord]:
    rows = [
        ("U01ALICE", "Alice Chen", "alice.chen@acme.com", "Engineering Director", None),
        ("U02BEN", "Ben Rivera", "ben.rivera@acme.com", "Senior Backend Engineer", "alice.chen@acme.com"),
        ("U03CARA", "Cara Patel", "cara.patel@acme.com", "Staff Platform Engineer", "alice.chen@acme.com"),
        ("U04DIEGO", "Diego Alvarez", "diego.alvarez@acme.com", "Payments Engineer", "alice.chen@acme.com"),
        ("U05ELENA", "Elena Kowalski", "elena.kowalski@acme.com", "Frontend Engineer", "alice.chen@acme.com"),
        ("U06FRANK", "Frank Osei", "frank.osei@acme.com", "Customer Support Lead", "alice.chen@acme.com"),
    ]
    return [
        MasterDataRecord(
            source="slack",
            external_id=ext_id,
            name=name,
            email=email,
            title=title,
            manager_email=manager,
        )
        for ext_id, name, email, title, manager in rows
    ]


JIRA_APP_ACCOUNT_TYPES = frozenset({"app"})
JIRA_PERSON_ACCOUNT_TYPES = frozenset({"atlassian", "customer"})
JIRA_NON_PERSON_NAME_HINTS = (
    "automation for jira",
    "jira spreadsheets",
    "atlassian assist",
    "jira service management",
    "system user",
    "add-on",
    "addon",
    "[bot]",
)


def _is_jira_person(user: dict) -> bool:
    """Keep real people; drop Jira apps, automation actors, and service accounts."""
    account_type = (user.get("accountType") or "atlassian").lower()
    if account_type in JIRA_APP_ACCOUNT_TYPES:
        return False
    if account_type not in JIRA_PERSON_ACCOUNT_TYPES:
        return False
    if user.get("active") is False:
        return False

    name = (user.get("displayName") or user.get("name") or "").lower()
    if any(hint in name for hint in JIRA_NON_PERSON_NAME_HINTS):
        return False
    if name.endswith(" bot") or name.startswith("bot "):
        return False
    return bool(name.strip())


def _synthetic_jira_email(account_id: str, display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-") or "user"
    short_id = re.sub(r"[^a-zA-Z0-9]", "", account_id)[:12] or "id"
    return f"{slug}+{short_id}@jira.import"


def _resolve_jira_user_email(
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
    account_id: str,
) -> str | None:
    try:
        response = requests.get(
            f"{base}/rest/api/3/user/email",
            params={"accountId": account_id},
            auth=auth,
            headers=headers,
            timeout=15,
        )
        if response.status_code == 200:
            email = (response.json().get("email") or "").strip()
            if email and "@" in email:
                return email
    except requests.RequestException:
        pass
    return None


def _fetch_jira_project_keys(
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
) -> list[str]:
    """Discover accessible project keys when none are configured."""
    response = requests.get(
        f"{base}/rest/api/3/project/search",
        params={"maxResults": 50, "orderBy": "key"},
        auth=auth,
        headers=headers,
        timeout=20,
    )
    if response.status_code >= 400:
        return []
    values = response.json().get("values", [])
    return [str(project["key"]).upper() for project in values if project.get("key")]


def _jira_search_issues(
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
    jql: str,
    *,
    fields: list[str] | None = None,
    max_issues: int = 100,
) -> list[dict]:
    """
    Search issues using Jira's enhanced JQL API.

    Legacy GET /rest/api/3/search is deprecated/removed on many Cloud sites.
    """
    issue_fields = fields or ["assignee", "reporter"]
    issues: list[dict] = []
    next_page_token: str | None = None
    errors: list[str] = []

    while len(issues) < max_issues:
        payload: dict[str, object] = {
            "jql": jql,
            "maxResults": min(50, max_issues - len(issues)),
            "fields": issue_fields,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        response = requests.post(
            f"{base}/rest/api/3/search/jql",
            json=payload,
            auth=auth,
            headers={**headers, "Content-Type": "application/json"},
            timeout=25,
        )
        if response.status_code == 401:
            raise ValueError(
                "Jira rejected these credentials (401). Re-verify your account "
                "email and API token."
            )
        if response.status_code >= 400:
            errors.append(f"search/jql {response.status_code}: {response.text[:180]}")
            break

        body = response.json()
        batch = body.get("issues", [])
        if not isinstance(batch, list):
            break
        issues.extend(batch)
        next_page_token = body.get("nextPageToken")
        if not next_page_token or not batch:
            break

    if issues:
        return issues

    # Last resort for tenants that still expose the legacy endpoint briefly
    legacy = requests.get(
        f"{base}/rest/api/3/search",
        params={
            "jql": jql,
            "maxResults": max_issues,
            "fields": ",".join(issue_fields),
        },
        auth=auth,
        headers=headers,
        timeout=25,
    )
    if legacy.status_code == 401:
        raise ValueError(
            "Jira rejected these credentials (401). Re-verify your account "
            "email and API token."
        )
    if legacy.status_code < 400:
        return legacy.json().get("issues", [])

    detail = errors[0] if errors else f"legacy search {legacy.status_code}"
    raise ValueError(f"Jira issue search failed: {detail}")


def _fetch_jira_issue_people(
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
    project_keys: list[str],
) -> list[dict]:
    """Collect unique human assignees/reporters from issues in projects."""
    if project_keys:
        quoted = ", ".join(project_keys)
        jql = f"project in ({quoted}) AND (assignee IS NOT EMPTY OR reporter IS NOT EMPTY)"
    else:
        jql = "(assignee IS NOT EMPTY OR reporter IS NOT EMPTY) ORDER BY updated DESC"

    issues = _jira_search_issues(base, auth, headers, jql)

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
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
    project_keys: list[str],
) -> list[dict]:
    """Fallback: humans who can be assigned in configured projects."""
    people: dict[str, dict] = {}
    for key in project_keys:
        response = requests.get(
            f"{base}/rest/api/3/user/assignable/multiProjectSearch",
            params={"projectKeys": key, "maxResults": 100},
            auth=auth,
            headers=headers,
            timeout=20,
        )
        if response.status_code == 401:
            raise ValueError(
                "Jira rejected these credentials (401). Re-verify your account "
                "email and API token."
            )
        if response.status_code >= 400:
            continue
        payload = response.json()
        if not isinstance(payload, list):
            continue
        for user in payload:
            if not _is_jira_person(user):
                continue
            account_id = user.get("accountId")
            if account_id and account_id not in people:
                people[account_id] = user
    return list(people.values())


def _fetch_jira_issue_assignees(
    base: str,
    auth: tuple[str, str],
    headers: dict[str, str],
    project_keys: list[str],
) -> list[dict]:
    """Backward-compatible alias for issue people fetch."""
    return _fetch_jira_issue_people(base, auth, headers, project_keys)


def _fetch_jira_users_live(
    site_url: str,
    auth_email: str,
    api_token: str,
    project_keys: str | None = None,
) -> list[MasterDataRecord]:
    """
    Import people assigned to Jira issues in configured projects.

    Only human assignees are included (accountType atlassian/customer).
    Apps like Automation for Jira and Jira Spreadsheets are excluded.
    """
    base = site_url.rstrip("/")
    auth = (auth_email.strip(), api_token.strip())
    headers = {"Accept": "application/json"}
    records: list[MasterDataRecord] = []
    seen: set[str] = set()

    keys = [
        key.strip().upper()
        for key in (project_keys or "").split(",")
        if key.strip()
    ]
    if not keys:
        keys = _fetch_jira_project_keys(base, auth, headers)

    def _append_user(user: dict, *, default_title: str = "Jira Assignee") -> None:
        if not _is_jira_person(user):
            return
        account_id = user.get("accountId") or user.get("account_id")
        if not account_id or account_id in seen:
            return

        display = (user.get("displayName") or user.get("name") or "").strip()
        email = (user.get("emailAddress") or user.get("email") or "").strip()
        if not email or "@" not in email:
            email = _resolve_jira_user_email(base, auth, headers, str(account_id))
        if not email:
            email = _synthetic_jira_email(str(account_id), display or str(account_id))

        seen.add(str(account_id))
        records.append(
            MasterDataRecord(
                source="jira",
                external_id=str(account_id),
                name=display or email.split("@")[0],
                email=email,
                title=default_title,
            )
        )

    search_error: str | None = None

    # Issue assignees/reporters — people on real tickets in your projects
    try:
        for person in _fetch_jira_issue_people(base, auth, headers, keys):
            _append_user(person)
    except (ValueError, requests.RequestException) as exc:
        search_error = str(exc)

    # Fallback: assignable humans in project(s), still filtered (no apps)
    if not records and keys:
        try:
            for person in _fetch_jira_assignable_humans(base, auth, headers, keys):
                _append_user(person, default_title="Jira Team Member")
        except (ValueError, requests.RequestException) as exc:
            if not search_error:
                search_error = str(exc)

    if not records:
        scope = f"project(s) {', '.join(keys)}" if keys else "your site"
        hint = (
            f" {search_error}" if search_error else ""
        )
        raise ValueError(
            f"Jira returned no human assignees for {scope}. "
            "Ensure issues have real people assigned (not automation apps)."
            f"{hint}"
        )
    return records


def _fetch_jira_users_fallback() -> list[MasterDataRecord]:
    rows = [
        ("jira-alice", "Alice Chen", "alice.chen@acme.com", "Engineering Manager", None),
        ("jira-ben", "Ben Rivera", "ben.rivera@acme.com", "Senior Software Engineer", "alice.chen@acme.com"),
        ("jira-cara", "Cara Patel", "cara.patel@acme.com", "Principal Engineer", "alice.chen@acme.com"),
        ("jira-diego", "Diego Alvarez", "diego.alvarez@acme.com", "Software Engineer II", "alice.chen@acme.com"),
    ]
    return [
        MasterDataRecord(
            source="jira",
            external_id=ext_id,
            name=name,
            email=email,
            title=title,
            manager_email=manager,
        )
        for ext_id, name, email, title, manager in rows
    ]


def _fetch_notion_users_fallback() -> list[MasterDataRecord]:
    rows = [
        ("notion-alice", "Alice Chen", "alice.chen@acme.com", "Head of Engineering", None),
        ("notion-ben", "Ben Rivera", "ben.rivera@acme.com", "Backend Engineer", "alice.chen@acme.com"),
        ("notion-cara", "Cara Patel", "cara.patel@acme.com", "Auth Platform Owner", "alice.chen@acme.com"),
    ]
    return [
        MasterDataRecord(
            source="notion",
            external_id=ext_id,
            name=name,
            email=email,
            title=title,
            manager_email=manager,
        )
        for ext_id, name, email, title, manager in rows
    ]


def _fetch_github_users_fallback_demo() -> list[MasterDataRecord]:
    return [
        MasterDataRecord(
            source="github",
            external_id=f"gh-{i}",
            name=name,
            email=email,
            title=title,
            manager_email=None,
        )
        for i, (name, email, title) in enumerate(
            [
                ("Alice Chen", "alice.chen@acme.com", "Engineering Lead"),
                ("Ben Rivera", "ben.rivera@acme.com", "Backend Contributor"),
                ("Cara Patel", "cara.patel@acme.com", "Platform Contributor"),
                ("Diego Alvarez", "diego.alvarez@acme.com", "Infra Contributor"),
            ],
            start=1,
        )
    ]


def _source_credentials_provided(source: str, creds: FetchUsersRequest) -> bool:
    if source == "slack":
        return bool((creds.slack_bot_token or "").strip())
    if source == "notion":
        return bool((creds.notion_integration_token or "").strip())
    if source == "github":
        repo_url = (creds.github_repository_url or "").strip()
        token = (creds.github_personal_access_token or "").strip()
        return bool(repo_url and token)
    if source == "jira":
        return bool((creds.jira_site_url or "").strip()) and bool(
            (creds.jira_auth_email or "").strip()
        ) and bool((creds.jira_api_token or "").strip())
    return False


def _fetch_source_records(
    source: str,
    credentials: FetchUsersRequest | None,
) -> list[MasterDataRecord]:
    creds = credentials or FetchUsersRequest(sources=[source])
    live_requested = _source_credentials_provided(source, creds)

    if source == "slack":
        token = (creds.slack_bot_token or "").strip()
        if token:
            try:
                return _fetch_slack_users_live(token)
            except (ValueError, requests.RequestException) as exc:
                raise ValueError(
                    f"Slack member import failed: {exc}"
                ) from exc
        if live_requested:
            raise ValueError("Slack bot token is missing.")
        return _fetch_slack_users_fallback()

    if source == "github":
        gh_config = get_github_config()
        repo_url = creds.github_repository_url or (
            gh_config.repository_url if gh_config else ""
        )
        token = creds.github_personal_access_token or (
            gh_config.personal_access_token if gh_config else ""
        )
        if repo_url.strip() and token.strip():
            try:
                return _fetch_github_org_members_live(repo_url, token)
            except (ValueError, requests.RequestException) as exc:
                raise ValueError(
                    f"GitHub member import failed: {exc}"
                ) from exc
        if live_requested:
            raise ValueError(
                "GitHub repository URL and personal access token are required."
            )
        return _fetch_github_users_fallback_demo()

    if source == "jira":
        site = (creds.jira_site_url or "").strip()
        auth_email = (creds.jira_auth_email or "").strip()
        token = (creds.jira_api_token or "").strip()
        project_keys = creds.jira_project_keys or ""
        if site and auth_email and token:
            try:
                return _fetch_jira_users_live(
                    site,
                    auth_email,
                    token,
                    project_keys=project_keys or None,
                )
            except (ValueError, requests.RequestException) as exc:
                raise ValueError(f"Jira member import failed: {exc}") from exc
        if live_requested:
            raise ValueError(
                "Jira site URL, account email, and API token are required."
            )
        return _fetch_jira_users_fallback()

    if source == "notion":
        token = (creds.notion_integration_token or "").strip()
        database_ids = (creds.notion_database_ids or "").strip()
        if token:
            try:
                live = fetch_notion_member_records(token, database_ids or None)
            except (ValueError, requests.RequestException) as exc:
                raise ValueError(
                    f"Notion member import failed: {exc}"
                ) from exc
            if not live:
                raise ValueError(
                    "Notion returned no workspace members. Share pages or databases "
                    "with your integration (••• → Connect to) and ensure the "
                    "integration can read user information."
                )
            return live
        if live_requested:
            raise ValueError("Notion integration token is missing.")
        return _fetch_notion_users_fallback()

    return []


def _pick_title(records: list[MasterDataRecord]) -> str:
    for source in SOURCE_PRIORITY:
        for record in records:
            if record.source == source and record.title.strip():
                return record.title.strip()
    return records[0].title.strip() if records else "Team Member"


def _pick_manager_email(records: list[MasterDataRecord]) -> str | None:
    for source in ("notion", "slack", "jira"):
        for record in records:
            if record.source == source and record.manager_email:
                return str(record.manager_email).lower()
    for record in records:
        if record.manager_email:
            return str(record.manager_email).lower()
    return None


def _merge_records(
    records: list[MasterDataRecord],
    *,
    tenant_id: uuid.UUID | None = None,
) -> MasterDataEmployee:
    email = records[0].email
    name = next((r.name for r in records if r.name.strip()), records[0].name)
    tenure = next(
        (r.tenure_years for r in records if r.tenure_years is not None),
        0.0,
    )
    providers = sorted({r.source for r in records})

    return MasterDataEmployee(
        id=_slug_id(str(email), tenant_id),
        name=name,
        email=email,
        role=_pick_title(records),
        manager_email=_pick_manager_email(records),
        tenure_years=tenure or 0.0,
        source_providers=providers,
    )


def _apply_hierarchy(
    employees: list[MasterDataEmployee],
    *,
    force_flat: bool = False,
) -> str:
    if force_flat:
        for employee in employees:
            employee.manager_id = None
            employee.manager_email = None
        return "flat"

    email_to_id = {str(emp.email).lower(): emp.id for emp in employees}
    resolved_links = 0
    for employee in employees:
        if employee.manager_email:
            manager_email = str(employee.manager_email).lower()
            if manager_email == str(employee.email).lower():
                employee.manager_id = None
                employee.manager_email = None
                continue
            employee.manager_id = email_to_id.get(manager_email)
            if employee.manager_id:
                resolved_links += 1
            else:
                employee.manager_id = None
        else:
            employee.manager_id = None

    if resolved_links == 0:
        for employee in employees:
            employee.manager_id = None
            employee.manager_email = None
        return "flat"

    return "structured"


def fetch_employee_master_data(
    sources: list[str],
    *,
    company: str = "Acme Company",
    credentials: FetchUsersRequest | None = None,
    flat_hierarchy: bool = False,
    tenant_id: uuid.UUID | None = None,
    skip_failed_sources: bool = False,
) -> EmployeeMasterDataResponse:
    """
    Import workspace members from connected platforms.

    Attempts to preserve reporting lines from Slack (profile manager / custom
    fields) and Notion people databases (Manager / Reports to relations).
    Falls back to a flat roster when no hierarchy metadata is found.
    """
    active_sources = [s for s in sources if s in ("slack", "jira", "notion", "github")]
    if not active_sources:
        raise ValueError(
            "Provide at least one source: slack, jira, notion, or github."
        )

    raw_records: list[MasterDataRecord] = []
    sources_queried: list[str] = []
    source_errors: list[str] = []
    for source in active_sources:
        try:
            records = _fetch_source_records(source, credentials)
        except ValueError as exc:
            if skip_failed_sources:
                source_errors.append(f"{source}: {exc}")
                continue
            raise
        if not records:
            message = f"{source}: no importable members returned."
            if skip_failed_sources:
                source_errors.append(message)
                continue
            raise ValueError(message)
        raw_records.extend(records)
        sources_queried.append(source)

    if not raw_records:
        if source_errors:
            raise ValueError("; ".join(source_errors))
        raise ValueError(
            "No members imported from the selected sources. "
            "Verify integration permissions and try again."
        )

    grouped: dict[str, list[MasterDataRecord]] = defaultdict(list)
    for record in raw_records:
        grouped[str(record.email).lower()].append(record)

    employees: list[MasterDataEmployee] = []
    for group in grouped.values():
        employees.append(_merge_records(group, tenant_id=tenant_id))

    hierarchy_mode = _apply_hierarchy(employees, force_flat=flat_hierarchy)
    employees.sort(key=lambda item: item.name.lower())
    roles = sorted({emp.role for emp in employees})

    return EmployeeMasterDataResponse(
        company=company,
        employees=employees,
        sources_queried=sources_queried,
        roles_discovered=roles,
        records_merged=len(raw_records),
        hierarchy_mode=hierarchy_mode,
        source_errors=source_errors,
    )
