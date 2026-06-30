from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlparse

import requests

from app.services.notion_client import fetch_notion_member_records
from app.schemas.employee_master import (
    EmployeeMasterDataResponse,
    FetchUsersRequest,
    MasterDataEmployee,
    MasterDataRecord,
)
from app.services.integration_sync import get_github_config, get_jira_config

SOURCE_PRIORITY = ("notion", "slack", "jira", "github")
MANAGER_FIELD_HINTS = ("manager", "reports to", "reporting", "reports_to", "lead")


def _slug_id(email: str) -> str:
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


def _fetch_slack_users_live(token: str) -> list[MasterDataRecord]:
    response = requests.get(
        "https://slack.com/api/users.list",
        headers={"Authorization": f"Bearer {token.strip()}"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise ValueError(
            f"Slack users.list failed: {payload.get('error', 'unknown_error')}"
        )

    slack_id_to_email: dict[str, str] = {}
    pending: list[tuple[dict, dict, str, str | None]] = []

    for member in payload.get("members", []):
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
            (creds.jira_api_token or "").strip()
        )
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
        if live_requested:
            return []
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


def _merge_records(records: list[MasterDataRecord]) -> MasterDataEmployee:
    email = records[0].email
    name = next((r.name for r in records if r.name.strip()), records[0].name)
    tenure = next(
        (r.tenure_years for r in records if r.tenure_years is not None),
        0.0,
    )
    providers = sorted({r.source for r in records})

    return MasterDataEmployee(
        id=_slug_id(str(email)),
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
    for source in active_sources:
        raw_records.extend(_fetch_source_records(source, credentials))

    if not raw_records:
        raise ValueError(
            "No members imported from the selected sources. "
            "Verify integration permissions and try again."
        )

    grouped: dict[str, list[MasterDataRecord]] = defaultdict(list)
    for record in raw_records:
        grouped[str(record.email).lower()].append(record)

    employees: list[MasterDataEmployee] = []
    for group in grouped.values():
        employees.append(_merge_records(group))

    hierarchy_mode = _apply_hierarchy(employees, force_flat=flat_hierarchy)
    employees.sort(key=lambda item: item.name.lower())
    roles = sorted({emp.role for emp in employees})

    return EmployeeMasterDataResponse(
        company=company,
        employees=employees,
        sources_queried=active_sources,
        roles_discovered=roles,
        records_merged=len(raw_records),
        hierarchy_mode=hierarchy_mode,
    )
