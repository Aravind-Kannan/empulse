"""Notion API helpers: search, database query, and member extraction."""

from __future__ import annotations

import logging
import re
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


def fetch_database_schema(token: str, database_id: str) -> dict[str, Any]:
    """Return the property schema for a Notion database."""
    response = requests.get(
        f"https://api.notion.com/v1/databases/{database_id}",
        headers=notion_headers(token),
        timeout=30,
    )
    if response.status_code >= 400:
        raise ValueError(
            f"Notion database fetch failed ({response.status_code}): "
            f"{response.text[:200]}"
        )
    return response.json().get("properties") or {}


def is_people_database_schema(properties: dict[str, Any]) -> bool:
    """Heuristic: roster DBs have email + name, or people + role columns."""
    has_name = any(prop.get("type") == "title" for prop in properties.values())
    if not has_name:
        return False

    has_email = any(prop.get("type") == "email" for prop in properties.values())
    if has_email:
        return True

    has_people = any(
        prop.get("type") == "people"
        for key, prop in properties.items()
        if any(
            hint in key.lower()
            for hint in ("person", "assignee", "member", "employee", "owner")
        )
    )
    has_role = any(
        prop.get("type") in ("select", "multi_select", "rich_text", "status")
        for key, prop in properties.items()
        if any(hint in key.lower() for hint in ("role", "title", "job", "position"))
    )
    return has_people and has_role


def discover_people_database_ids(token: str) -> list[str]:
    """Return database IDs that look like people / team rosters."""
    people_ids: list[str] = []
    for database_id in discover_database_ids(token):
        try:
            properties = fetch_database_schema(token, database_id)
        except ValueError as exc:
            logger.warning("Skipping Notion database %s: %s", database_id, exc)
            continue
        if is_people_database_schema(properties):
            people_ids.append(database_id)
    return people_ids


def _row_people_emails(props: dict[str, Any]) -> list[str]:
    emails: list[str] = []
    for prop in props.values():
        if prop.get("type") == "people":
            emails.extend(_prop_people_emails(prop))
    return emails


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
        row_people_emails = _row_people_emails(props)
        if not email and manager_prop:
            manager_people_emails = _prop_people_emails(manager_prop)
            if manager_people_emails:
                email = manager_people_emails[0]
        if not email and row_people_emails:
            email = row_people_emails[0]
        if not email:
            # Skip non-person rows (expense trackers, task lists, etc.).
            continue

        email = email.lower()
        page_id = str(page.get("id", email))
        page_id_to_email[page_id] = email

        relation_ids = _prop_relation_ids(manager_prop)
        people_emails = _prop_people_emails(manager_prop) or row_people_emails
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

    Without explicit ``database_ids``, imports workspace users only (Notion
    Users API). When IDs are omitted but auto-discovery is desired, only
    databases that look like people rosters are queried — not every shared DB.
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


EXPERTISE_FIELD_HINTS = ("expertise", "skills", "specialt", "topic")
from app.services.github_component_display import display_folder, parse_github_auto_tag

DOC_FIELD_HINTS = ("runbook", "architecture", "playbook", "wiki", "doc", "handover")
COMPONENT_FIELD_HINTS = ("component", "system", "service", "product", "area")
OWNER_FIELD_HINTS = ("owner", "author", "maintainer", "doc owner")
VERIFIED_FIELD_HINTS = ("last verified", "last_verified", "verified", "last reviewed")
OWNERSHIP_TEMPLATE_HINTS = ("ownership transfer", "living runbook", "handover pack")


def _extended_path_component_map(path_component_map: dict[str, str] | None) -> dict[str, str]:
    """
    Normalize tenant GitHub `path_component_map` prefixes from provisioning.

    Nested repo paths (e.g. `notion-docs/design/foo.md`) resolve via longest-prefix
    match — no repo-specific folder aliases.
    """
    if not path_component_map:
        return {}
    extended: dict[str, str] = {}
    for prefix, component_id in path_component_map.items():
        cleaned = prefix.strip().strip("/")
        if not cleaned:
            continue
        extended.setdefault(cleaned, component_id)
        extended.setdefault(f"{cleaned}/", component_id)
    return extended


def _auto_tag_match_needles(description: str | None) -> list[str]:
    """Derive match needles from `AUTO:github:owner/repo:path/` component descriptions."""
    parsed = parse_github_auto_tag(description)
    if not parsed:
        return []
    folder = display_folder(parsed[1])
    if not folder:
        return []
    needles = [folder, folder.replace("-", " "), folder.replace("/", " ")]
    needles.extend(part for part in folder.split("/") if part)
    return needles


def _component_match_entries(
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    component_descriptions: dict[str, str] | None = None,
) -> list[tuple[int, str, str]]:
    """Return (priority, needle, component_id) sorted highest priority first."""
    entries: list[tuple[int, str, str]] = []
    suffix_to_ids: dict[str, list[str]] = {}

    for component_id, name in component_names.items():
        name_lower = name.lower().strip()
        if name_lower:
            entries.append((len(name_lower), name_lower, component_id))
        if " / " in name:
            suffix = name.rsplit(" / ", 1)[-1].strip().lower()
            if suffix:
                suffix_to_ids.setdefault(suffix, []).append(component_id)
                entries.append((len(suffix) + 200, suffix, component_id))

        for needle in _auto_tag_match_needles(
            (component_descriptions or {}).get(component_id)
        ):
            entries.append((len(needle) + 210, needle.lower(), component_id))

    for suffix, ids in suffix_to_ids.items():
        slug = re.sub(r"[^a-z0-9]+", "-", suffix).strip("-")
        if slug and slug != suffix:
            for component_id in ids:
                entries.append((len(slug) + 150, slug, component_id))

    for prefix, component_id in _extended_path_component_map(path_component_map).items():
        norm = prefix.strip("/").lower()
        if not norm:
            continue
        entries.append((len(norm) + 180, norm, component_id))
        entries.append((len(norm) + 170, norm.replace("-", " "), component_id))
        entries.append((len(norm) + 160, norm.replace("/", " "), component_id))

    entries.sort(key=lambda row: row[0], reverse=True)
    return entries


def match_component_for_document(
    title: str,
    *,
    path_hint: str = "",
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    component_descriptions: dict[str, str] | None = None,
) -> str | None:
    """Resolve a Notion page or repo doc path to an org component id."""
    haystack = f"{path_hint} {title}".lower().replace("_", " ").replace("-", " ")

    extended_map = _extended_path_component_map(path_component_map)
    if path_hint:
        normalized_path = path_hint.strip().lstrip("/").lower()
        best: tuple[int, str] | None = None
        for prefix, component_id in extended_map.items():
            norm_prefix = prefix.strip("/").lower()
            if not norm_prefix:
                continue
            if normalized_path == norm_prefix or normalized_path.startswith(f"{norm_prefix}/"):
                if best is None or len(norm_prefix) > best[0]:
                    best = (len(norm_prefix), component_id)
        if best:
            return best[1]

    for priority, needle, component_id in _component_match_entries(
        component_names,
        path_component_map,
        component_descriptions,
    ):
        if needle and needle in haystack:
            return component_id

    return None


def _prop_multi_select(prop: dict | None) -> list[str]:
    if not prop or prop.get("type") != "multi_select":
        return []
    return [
        str(item.get("name", "")).strip()
        for item in (prop.get("multi_select") or [])
        if item.get("name")
    ]


def _prop_date_value(prop: dict | None) -> str | None:
    if not prop or prop.get("type") != "date":
        return None
    date_value = prop.get("date") or {}
    return date_value.get("start")


def _page_url(page_id: str) -> str:
    clean = page_id.replace("-", "")
    return f"https://www.notion.so/{clean}"


def _is_archived(page: dict[str, Any]) -> bool:
    return bool(page.get("archived"))


def parse_people_expertise_rows(page_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract Guru-style expertise tags from People DB rows."""
    expertise_rows: list[dict[str, Any]] = []
    for page in page_rows:
        props = page.get("properties") or {}
        email_prop = _find_property(props, "email", "work email", "mail")
        name_prop = _find_property(props, "name", "employee", "person")
        email = _prop_text(email_prop).lower()
        if not email:
            continue
        tags: list[str] = []
        for key, prop in props.items():
            label = key.lower()
            if any(hint in label for hint in EXPERTISE_FIELD_HINTS):
                tags.extend(_prop_multi_select(prop))
        if tags:
            expertise_rows.append(
                {
                    "email": email,
                    "name": _prop_text(name_prop) or _page_title(page) or email,
                    "tags": sorted(set(tags)),
                    "page_id": str(page.get("id", "")),
                }
            )
    return expertise_rows


def parse_document_pages(
    pages: list[dict[str, Any]],
    *,
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    component_descriptions: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Normalize wiki pages and database rows into doc inventory dicts."""
    docs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_page(page: dict[str, Any], *, default_kind: str = "runbook") -> None:
        page_id = str(page.get("id", "") or page.get("page_id", ""))
        if not page_id or page_id in seen_ids or _is_archived(page):
            return
        props = page.get("properties") or {}
        title = _page_title(page) if page.get("object") else str(page.get("title") or "")
        if not title and page.get("object") == "page":
            parent = page.get("parent") or {}
            if parent.get("type") == "database_id":
                title = _prop_text(_find_property(props, "name", "title")) or "Untitled"
        if not title:
            return

        component_id: str | None = page.get("component_id")
        component_prop = _find_property(props, *COMPONENT_FIELD_HINTS)
        relation_ids = _prop_relation_ids(component_prop)
        if relation_ids:
            component_id = relation_ids[0]

        title_lower = title.lower()
        path_hint = str(page.get("repo_path") or "")
        if not component_id:
            component_id = match_component_for_document(
                title,
                path_hint=path_hint,
                component_names=component_names,
                path_component_map=path_component_map,
                component_descriptions=component_descriptions,
            )

        owner_prop = _find_property(props, *OWNER_FIELD_HINTS)
        owner_emails = _prop_people_emails(owner_prop)
        verified_prop = _find_property(props, *VERIFIED_FIELD_HINTS)
        last_verified = _prop_date_value(verified_prop)

        page_kind = default_kind
        if any(hint in title_lower for hint in OWNERSHIP_TEMPLATE_HINTS):
            page_kind = "ownership_template"
        elif "postmortem" in title_lower:
            page_kind = "postmortem"
        elif any(hint in title_lower for hint in DOC_FIELD_HINTS):
            page_kind = "runbook"

        docs.append(
            {
                "page_id": page_id,
                "title": title,
                "page_url": str(
                    page.get("page_url") or page.get("url") or _page_url(page_id)
                ),
                "last_edited_at": page.get("last_edited_time"),
                "component_id": component_id,
                "owner_emails": owner_emails,
                "page_kind": page_kind,
                "last_verified_at": last_verified,
                "is_archived": _is_archived(page),
            }
        )
        seen_ids.add(page_id)

    for page in pages:
        add_page(page)

    return docs


def fetch_notion_document_inventory(
    token: str,
    database_ids: str | None,
    *,
    component_names: dict[str, str],
    path_component_map: dict[str, str] | None = None,
    component_descriptions: dict[str, str] | None = None,
    repo_doc_pages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Return (document_pages, people_expertise_rows).

    Combines Notion search results with configured database rows.
    """
    cleaned_token = token.strip()
    if not cleaned_token:
        return [], []

    explicit_ids = [
        item.strip() for item in (database_ids or "").split(",") if item.strip()
    ]
    ids = explicit_ids or discover_database_ids(cleaned_token)

    db_rows: list[dict[str, Any]] = []
    for database_id in ids:
        try:
            db_rows.extend(query_database_pages(cleaned_token, database_id))
        except ValueError as exc:
            logger.warning("Skipping Notion database %s: %s", database_id, exc)

    try:
        search_pages = search_notion_objects(cleaned_token, object_type="page")
    except ValueError as exc:
        logger.warning("Notion page search failed: %s", exc)
        search_pages = []

    docs = parse_document_pages(
        search_pages + db_rows + list(repo_doc_pages or []),
        component_names=component_names,
        path_component_map=path_component_map,
        component_descriptions=component_descriptions,
    )
    expertise = parse_people_expertise_rows(db_rows)
    return docs, expertise


def load_fixture_document_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import json
    from pathlib import Path

    fixture_path = (
        Path(__file__).resolve().parent.parent.parent
        / "tests"
        / "fixtures"
        / "notion_doc_inventory.json"
    )
    payload = json.loads(fixture_path.read_text())
    return payload.get("pages", []), payload.get("people_expertise", [])

