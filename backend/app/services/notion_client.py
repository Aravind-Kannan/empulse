"""Notion API helpers: search, database query, and member extraction."""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.schemas.employee_master import MasterDataRecord
from app.ssl import configure_ssl

configure_ssl()

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
MANAGER_FIELD_HINTS = ("manager", "reports to", "reporting", "reports_to", "lead")


def notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token.strip()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def search_notion_objects(
    token: str,
    *,
    object_type: str | None = None,
) -> list[dict[str, Any]]:
    """Paginate Notion search and return all matching objects."""
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if object_type:
            body["filter"] = {"property": "object", "value": object_type}
        if cursor:
            body["start_cursor"] = cursor
        response = requests.post(
            "https://api.notion.com/v1/search",
            headers=notion_headers(token),
            json=body,
            timeout=30,
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Notion search failed ({response.status_code}): "
                f"{response.text[:200]}"
            )
        payload = response.json()
        results.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return results


def discover_database_ids(token: str) -> list[str]:
    """Return IDs of all databases the integration can access."""
    databases = search_notion_objects(token, object_type="database")
    return [str(item["id"]) for item in databases if item.get("id")]


def query_database_pages(token: str, database_id: str) -> list[dict[str, Any]]:
    """Fetch all rows from a Notion database."""
    page_rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        response = requests.post(
            f"https://api.notion.com/v1/databases/{database_id}/query",
            headers=notion_headers(token),
            json=body,
            timeout=30,
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Notion database query failed ({response.status_code}): "
                f"{response.text[:200]}"
            )
        payload = response.json()
        page_rows.extend(payload.get("results") or [])
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return page_rows


def fetch_notion_workspace_users(token: str) -> list[MasterDataRecord]:
    """List workspace members via Notion Users API."""
    records: list[MasterDataRecord] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        response = requests.get(
            "https://api.notion.com/v1/users",
            headers=notion_headers(token),
            params=params,
            timeout=30,
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Notion users list failed ({response.status_code}): "
                f"{response.text[:200]}"
            )
        payload = response.json()
        for user in payload.get("results") or []:
            if user.get("type") != "person":
                continue
            user_id = str(user.get("id", ""))
            if not user_id:
                continue
            person = user.get("person") or {}
            email = (person.get("email") or "").strip().lower()
            name = (user.get("name") or "").strip() or "Notion User"
            if not email:
                email = f"notion-user-{user_id.replace('-', '')[:12]}@example.com"
            records.append(
                MasterDataRecord(
                    source="notion",
                    external_id=user_id,
                    name=name,
                    email=email,
                    title="Workspace Member",
                    manager_email=None,
                )
            )
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor")
    return records


def _prop_text(prop: dict | None) -> str:
    if not prop:
        return ""
    prop_type = prop.get("type")
    if prop_type == "title":
        parts = prop.get("title") or []
        return "".join(part.get("plain_text", "") for part in parts).strip()
    if prop_type == "rich_text":
        parts = prop.get("rich_text") or []
        return "".join(part.get("plain_text", "") for part in parts).strip()
    if prop_type == "select":
        selected = prop.get("select")
        return selected.get("name", "") if selected else ""
    if prop_type == "email":
        return (prop.get("email") or "").strip()
    if prop_type == "url":
        return (prop.get("url") or "").strip()
    return ""


def _prop_relation_ids(prop: dict | None) -> list[str]:
    if not prop or prop.get("type") != "relation":
        return []
    return [item.get("id") for item in (prop.get("relation") or []) if item.get("id")]


def _prop_people_emails(prop: dict | None) -> list[str]:
    if not prop or prop.get("type") != "people":
        return []
    emails: list[str] = []
    for person in prop.get("people") or []:
        if person.get("type") == "person":
            email = (person.get("person") or {}).get("email")
            if email:
                emails.append(str(email).lower())
    return emails


def _find_property(props: dict, *hints: str) -> dict | None:
    for key, prop in props.items():
        label = key.lower()
        if any(hint in label for hint in hints):
            return prop
    return None


def _page_title(page: dict[str, Any]) -> str:
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            title = _prop_text(prop)
            if title:
                return title
    return ""


def parse_database_rows_to_records(page_rows: list[dict[str, Any]]) -> list[MasterDataRecord]:
    """Extract member records from Notion database rows."""
    if not page_rows:
        return []

    page_id_to_email: dict[str, str] = {}
    pending: list[tuple[str, str, str, str, list[str], list[str]]] = []

    for page in page_rows:
        props = page.get("properties") or {}
        name_prop = _find_property(props, "name", "employee", "person")
        email_prop = _find_property(props, "email", "work email", "mail")
        role_prop = _find_property(props, "role", "title", "job", "position")
        manager_prop = _find_property(
            props,
            "manager",
            "reports to",
            "reporting",
            "lead",
        )

        name = _prop_text(name_prop) or _page_title(page) or "Notion Member"
        email = _prop_text(email_prop)
        if not email and manager_prop:
            people_emails = _prop_people_emails(manager_prop)
            if people_emails:
                email = people_emails[0]
        if not email:
            page_id = str(page.get("id", ""))
            if not page_id:
                continue
            email = f"notion-{page_id.replace('-', '')[:12]}@example.com"

        email = email.lower()
        page_id = str(page.get("id", email))
        page_id_to_email[page_id] = email

        relation_ids = _prop_relation_ids(manager_prop)
        people_emails = _prop_people_emails(manager_prop)
        pending.append(
            (
                page_id,
                name,
                email,
                _prop_text(role_prop) or "Team Member",
                relation_ids,
                people_emails,
            )
        )

    records: list[MasterDataRecord] = []
    for page_id, name, email, title, relation_ids, people_emails in pending:
        manager_email: str | None = None
        if people_emails:
            manager_email = people_emails[0]
        elif relation_ids:
            for rel_id in relation_ids:
                if rel_id in page_id_to_email:
                    manager_email = page_id_to_email[rel_id]
                    break

        records.append(
            MasterDataRecord(
                source="notion",
                external_id=page_id,
                name=name,
                email=email,
                title=title,
                manager_email=manager_email if manager_email != email else None,
            )
        )
    return records


def _merge_notion_records(
    *record_groups: list[MasterDataRecord],
) -> list[MasterDataRecord]:
    """Merge Notion records by email; earlier groups win on conflicts."""
    by_email: dict[str, MasterDataRecord] = {}
    for group in record_groups:
        for record in group:
            key = record.email.lower()
            existing = by_email.get(key)
            if not existing:
                by_email[key] = record
                continue
            if existing.manager_email is None and record.manager_email:
                by_email[key] = record
            elif "@example.com" in existing.email and "@example.com" not in record.email:
                by_email[key] = record
    return list(by_email.values())


def fetch_notion_member_records(
    token: str,
    database_ids: str | None = None,
) -> list[MasterDataRecord]:
    """
    Import members from Notion.

    Queries shared databases when available, then supplements with workspace
    users from the Notion Users API so a people database is not required.
    """
    cleaned_token = token.strip()
    if not cleaned_token:
        return []

    explicit_ids = [
        item.strip()
        for item in (database_ids or "").split(",")
        if item.strip()
    ]
    ids = explicit_ids
    if not ids:
        try:
            ids = discover_database_ids(cleaned_token)
        except ValueError as exc:
            logger.warning("Notion database discovery failed: %s", exc)
            ids = []

    db_records: list[MasterDataRecord] = []
    if ids:
        all_rows: list[dict[str, Any]] = []
        for database_id in ids:
            try:
                all_rows.extend(query_database_pages(cleaned_token, database_id))
            except ValueError as exc:
                logger.warning("Skipping Notion database %s: %s", database_id, exc)
        db_records = parse_database_rows_to_records(all_rows)

    workspace_records = fetch_notion_workspace_users(cleaned_token)
    return _merge_notion_records(db_records, workspace_records)


def count_accessible_resources(token: str) -> tuple[int, int]:
    """Return (database_count, page_count) visible to the integration."""
    databases = search_notion_objects(token, object_type="database")
    pages = search_notion_objects(token, object_type="page")
    return len(databases), len(pages)
