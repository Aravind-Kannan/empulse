"""Live credential checks against Slack and Notion APIs."""

from __future__ import annotations

import requests

from app.services.employee_master_fetch import _format_slack_api_error
from app.services.notion_client import NOTION_VERSION, count_accessible_resources


def validate_notion_token(token: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Notion integration token is required.")
    if not cleaned.startswith("secret_") and not cleaned.startswith("ntn_"):
        raise ValueError(
            "Notion token should start with secret_ or ntn_. "
            "Copy the Internal Integration Secret from notion.so/my-integrations."
        )

    try:
        response = requests.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {cleaned}",
                "Notion-Version": NOTION_VERSION,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not reach Notion API: {exc}") from exc

    if response.status_code == 401:
        raise ValueError(
            "Notion rejected this token (401). Generate a new Internal Integration Secret "
            "and ensure the integration is not revoked."
        )
    if response.status_code >= 400:
        detail = response.text[:200] if response.text else response.reason
        raise ValueError(f"Notion API error ({response.status_code}): {detail}")

    payload = response.json()
    name = payload.get("name") or payload.get("id") or "workspace bot"
    try:
        db_count, page_count = count_accessible_resources(cleaned)
        return (
            f"Notion token valid — authenticated as {name}. "
            f"Found {db_count} database(s) and {page_count} page(s) accessible."
        )
    except ValueError:
        return f"Notion token valid — authenticated as {name}."


def validate_jira_credentials(
    site_url: str,
    api_token: str,
    account_email: str = "",
) -> tuple[str, str]:
    """Verify Jira token and return the canonical Atlassian account email."""
    from app.services.jira_client import _auth_headers, _normalize_site_url

    token = api_token.strip()
    if not token:
        raise ValueError("Jira API token is required.")

    email = account_email.strip()
    if not email:
        raise ValueError(
            "Atlassian account email is required with the API token "
            "(use the email for your Atlassian account, not your Empulse login)."
        )

    config = __import__(
        "app.schemas.integrations", fromlist=["JiraConfigRequest"]
    ).JiraConfigRequest(
        site_url=site_url,
        api_token=token,
        account_email=email,
    )
    url = f"{_normalize_site_url(site_url)}/rest/api/3/myself"
    try:
        response = requests.get(
            url,
            headers=_auth_headers(config),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not reach Jira API: {exc}") from exc

    if response.status_code == 401:
        raise ValueError(
            "Jira rejected these credentials (401). Confirm the API token is valid "
            "and the account email matches the Atlassian account that created the token."
        )
    if response.status_code >= 400:
        detail = response.text[:200] if response.text else response.reason
        raise ValueError(f"Jira API error ({response.status_code}): {detail}")

    payload = response.json()
    resolved_email = (payload.get("emailAddress") or email).strip()
    display_name = (payload.get("displayName") or resolved_email).strip()
    return (
        resolved_email,
        f"Jira token valid — authenticated as {display_name} ({resolved_email}).",
    )


def validate_slack_bot_token(token: str) -> str:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("Slack bot token is required.")
    if not cleaned.startswith("xoxb-"):
        raise ValueError(
            "Slack bot token should start with xoxb-. "
            "Create a Bot User OAuth Token under api.slack.com/apps."
        )

    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {cleaned}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not reach Slack API: {exc}") from exc

    payload = response.json()
    if not payload.get("ok"):
        error = payload.get("error", "unknown_error")
        raise ValueError(
            f"Slack rejected this token ({error}). "
            "Reinstall the app to your workspace and copy a fresh xoxb- token."
        )

    team = payload.get("team") or "workspace"
    bot = payload.get("user") or "bot"

    try:
        users_response = requests.get(
            "https://slack.com/api/users.list",
            headers={"Authorization": f"Bearer {cleaned}"},
            params={"limit": "1"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not verify Slack member import scopes: {exc}") from exc

    users_payload = users_response.json()
    if not users_payload.get("ok"):
        raise ValueError(
            _format_slack_api_error(users_payload.get("error", "unknown_error"))
        )

    return f"Slack token valid — {bot} on {team}. Member import scopes verified."
