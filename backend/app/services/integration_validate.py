"""Live credential checks against Slack and Notion APIs."""

from __future__ import annotations

import requests

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
    return f"Slack token valid — {bot} on {team}."
