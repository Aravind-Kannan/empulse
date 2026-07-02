"""Live credential checks against Slack, Notion, Jira, and GitHub APIs."""

from __future__ import annotations

import requests

from app.services.employee_master_fetch import _format_slack_api_error
from app.services.github_client import parse_repository_url
from app.services.notion_client import NOTION_VERSION, count_accessible_resources
from app.services.slack_client import discover_channel_ids


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


def validate_github_credentials(
    personal_access_token: str,
    *,
    repository_url: str = "",
    repository_urls: list[str] | None = None,
    branch_target: str = "main",
    branch_targets: list[str] | None = None,
    sync_all_branches: bool = False,
) -> str:
    """Verify PAT access and selected repositories/branches."""
    token = personal_access_token.strip()
    if not token:
        raise ValueError("GitHub personal access token is required.")

    urls = [url.strip() for url in (repository_urls or []) if url.strip()]
    if not urls and repository_url.strip():
        urls = [repository_url.strip()]
    if not urls:
        raise ValueError("Select at least one GitHub repository to sync.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    verified: list[str] = []
    for repo_url in urls:
        try:
            owner, repo = parse_repository_url(repo_url)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        api_repo_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            response = requests.get(api_repo_url, headers=headers, timeout=20)
        except requests.RequestException as exc:
            raise ValueError(f"Could not reach GitHub API: {exc}") from exc

        if response.status_code == 401:
            raise ValueError(
                "GitHub rejected this token (401). Generate a new personal access token "
                "with repository read access."
            )
        if response.status_code == 404:
            raise ValueError(
                f"Repository '{owner}/{repo}' was not found or this token cannot access it. "
                "Confirm the repository is selected and that your PAT is authorized for it."
            )
        if response.status_code == 403:
            detail = response.text[:160] if response.text else response.reason
            raise ValueError(
                f"GitHub denied access to '{owner}/{repo}' (403). "
                f"Check token scopes and repository permissions. {detail}"
            )
        if response.status_code >= 400:
            detail = response.text[:200] if response.text else response.reason
            raise ValueError(f"GitHub API error ({response.status_code}): {detail}")

        payload = response.json()
        full_name = payload.get("full_name") or f"{owner}/{repo}"
        default_branch = (payload.get("default_branch") or "main").strip()
        verified.append(full_name)

        if sync_all_branches:
            continue

        branches = [branch.strip() for branch in (branch_targets or []) if branch.strip()]
        if not branches and branch_target.strip():
            branches = [branch_target.strip()]
        if not branches:
            branches = [default_branch]

        for branch in branches:
            branch_resp = requests.get(
                f"{api_repo_url}/branches/{branch}",
                headers=headers,
                timeout=15,
            )
            if branch_resp.status_code == 404:
                raise ValueError(
                    f"Branch '{branch}' was not found on {full_name}. "
                    f"The default branch is '{default_branch}'."
                )
            if branch_resp.status_code >= 400:
                detail = branch_resp.text[:160] if branch_resp.text else branch_resp.reason
                raise ValueError(
                    f"Could not verify branch '{branch}' on {full_name}: {detail}"
                )

    repo_summary = ", ".join(verified)
    if sync_all_branches:
        branch_note = " All branches will be synced."
    else:
        branch_list = [branch.strip() for branch in (branch_targets or []) if branch.strip()]
        if not branch_list and branch_target.strip():
            branch_list = [branch_target.strip()]
        branch_note = (
            f" Target branches: {', '.join(branch_list)}."
            if branch_list
            else ""
        )

    return (
        f"GitHub token valid — verified access to {len(verified)} "
        f"repositor{'y' if len(verified) == 1 else 'ies'} ({repo_summary}).{branch_note}"
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

    try:
        channel_count = len(discover_channel_ids(cleaned))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    return (
        f"Slack token valid — {bot} on {team}. "
        f"Found {channel_count} accessible channel(s)."
    )
