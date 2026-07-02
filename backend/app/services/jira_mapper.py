"""Map Jira issues to org chart components (ERA Step 05)."""

from __future__ import annotations

from app.schemas.integrations import JiraConfigRequest
from app.services.jira_types import JiraIssueActivity


def map_issue_to_component(
    issue: JiraIssueActivity,
    config: JiraConfigRequest,
    *,
    valid_component_ids: set[str],
) -> str | None:
    if issue.component_id:
        return issue.component_id

    for label in issue.labels:
        normalized = label.strip().lower()
        if normalized.startswith("component:"):
            candidate = normalized.split(":", 1)[1].strip()
            mapped = config.label_component_map.get(candidate) or config.label_component_map.get(
                f"component:{candidate}"
            )
            if mapped and mapped in valid_component_ids:
                return mapped
            if candidate in valid_component_ids:
                return candidate

    for jira_name in issue.jira_component_names:
        mapped = config.component_field_map.get(jira_name)
        if mapped and mapped in valid_component_ids:
            return mapped

    project_mapped = config.project_component_map.get(issue.project_key.upper())
    if project_mapped and project_mapped in valid_component_ids:
        return project_mapped

    default = config.default_component_id
    if default and default in valid_component_ids:
        return default

    return None


def issue_browse_url(site_url: str, issue_key: str) -> str:
    base = site_url.strip().rstrip("/")
    return f"{base}/browse/{issue_key}"
