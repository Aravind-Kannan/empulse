"""Resolve Jira Cloud user emails when issue/search payloads omit emailAddress."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

SYNTHETIC_JIRA_EMAIL_DOMAIN = "jira.import"


def is_synthetic_jira_email(email: str | None) -> bool:
    return bool(email and str(email).lower().endswith(f"@{SYNTHETIC_JIRA_EMAIL_DOMAIN}"))


def normalize_person_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _parse_email_value(value: Any) -> str | None:
    if isinstance(value, str):
        email = value.strip()
        if email and "@" in email:
            return email
        return None
    if isinstance(value, dict):
        for key in ("email", "emailAddress"):
            email = (value.get(key) or "").strip()
            if email and "@" in email:
                return email
    return None


def _request_kwargs(
    auth: tuple[str, str] | None,
    headers: dict[str, str] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"timeout": 15}
    if auth and auth[0].strip() and auth[1].strip():
        kwargs["auth"] = auth
    if headers:
        kwargs["headers"] = headers
    return kwargs


def resolve_jira_user_email(
    base: str,
    account_id: str,
    *,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    display_name: str | None = None,
) -> str | None:
    """Resolve one user's email via Jira admin email APIs and profile search."""
    account_id = account_id.strip()
    if not account_id:
        return None

    site = base.rstrip("/")
    req = _request_kwargs(auth, headers)

    try:
        response = requests.get(
            f"{site}/rest/api/3/user/email",
            params={"accountId": account_id},
            **req,
        )
        if response.status_code == 200:
            email = _parse_email_value(response.json())
            if email:
                return email
    except requests.RequestException:
        pass

    try:
        response = requests.get(
            f"{site}/rest/api/3/user",
            params={"accountId": account_id},
            **req,
        )
        if response.status_code == 200:
            email = _parse_email_value(response.json())
            if email:
                return email
    except requests.RequestException:
        pass

    if display_name:
        try:
            response = requests.get(
                f"{site}/rest/api/3/user/search",
                params={"query": display_name.strip(), "maxResults": 20},
                **req,
            )
            if response.status_code == 200:
                for user in response.json() or []:
                    if not isinstance(user, dict):
                        continue
                    if user.get("accountId") != account_id:
                        continue
                    email = _parse_email_value(user)
                    if email:
                        return email
        except requests.RequestException:
            pass

    return None


def bulk_resolve_jira_user_emails(
    base: str,
    account_ids: list[str],
    *,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Resolve emails in bulk via GET /rest/api/3/user/email/bulk."""
    unique_ids = [aid.strip() for aid in dict.fromkeys(account_ids) if aid and aid.strip()]
    if not unique_ids:
        return {}

    site = base.rstrip("/")
    req = _request_kwargs(auth, headers)
    resolved: dict[str, str] = {}

    chunk_size = 50
    for start in range(0, len(unique_ids), chunk_size):
        batch = unique_ids[start : start + chunk_size]
        params: list[tuple[str, str]] = [("accountId", account_id) for account_id in batch]
        try:
            response = requests.get(
                f"{site}/rest/api/3/user/email/bulk",
                params=params,
                **req,
            )
        except requests.RequestException:
            continue

        if response.status_code != 200:
            logger.debug(
                "Jira bulk email lookup failed (%s) for %d account ids",
                response.status_code,
                len(batch),
            )
            continue

        payload = response.json()
        rows: list[Any]
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            values = payload.get("values")
            rows = values if isinstance(values, list) else [payload]
        else:
            rows = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            account_id = (row.get("accountId") or "").strip()
            email = _parse_email_value(row)
            if account_id and email:
                resolved[account_id] = email

    return resolved


def enrich_jira_users_with_emails(
    base: str,
    users: list[dict],
    *,
    auth: tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    auth_user_account_id: str | None = None,
    auth_user_email: str | None = None,
) -> dict[str, str]:
    """
    Return accountId -> email for Jira users, using inline emailAddress when present
    and bulk/single resolution for the rest.
    """
    emails: dict[str, str] = {}
    pending_ids: list[str] = []

    for user in users:
        account_id = (user.get("accountId") or user.get("account_id") or "").strip()
        if not account_id:
            continue
        inline = _parse_email_value(user.get("emailAddress") or user.get("email"))
        if inline:
            emails[account_id] = inline
        else:
            pending_ids.append(account_id)

    if pending_ids:
        emails.update(
            bulk_resolve_jira_user_emails(
                base,
                pending_ids,
                auth=auth,
                headers=headers,
            )
        )

    still_pending = [
        account_id
        for account_id in pending_ids
        if account_id not in emails
    ]
    user_by_id = {
        (user.get("accountId") or user.get("account_id") or "").strip(): user
        for user in users
        if isinstance(user, dict)
    }
    for account_id in still_pending:
        display = (
            user_by_id.get(account_id, {}).get("displayName")
            or user_by_id.get(account_id, {}).get("name")
            or ""
        )
        email = resolve_jira_user_email(
            base,
            account_id,
            auth=auth,
            headers=headers,
            display_name=str(display),
        )
        if email:
            emails[account_id] = email

    if auth_user_account_id and auth_user_email:
        auth_id = auth_user_account_id.strip()
        auth_email = auth_user_email.strip()
        if auth_id and auth_email and "@" in auth_email and auth_id not in emails:
            emails[auth_id] = auth_email

    return emails
