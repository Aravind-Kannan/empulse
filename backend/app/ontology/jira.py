"""Jira → canonical ontology normalizers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ontology.canonical import (
    CanonicalComponentRef,
    CanonicalPersonRef,
    CanonicalWorkItem,
)
from app.schemas.integrations import JiraConfigRequest
from app.services.identity_resolver import resolve_author_employee_id
from app.services.jira_types import JiraIssueActivity


def normalize_jira_issue(
    issue: JiraIssueActivity,
    *,
    config: JiraConfigRequest,
    db: Session,
    tenant_id: uuid.UUID,
    components_by_id: dict,
    project_filter: set[str],
) -> CanonicalWorkItem | None:
    if project_filter and issue.project_key not in project_filter:
        return None
    if issue.is_done and not issue.is_bug_or_incident:
        return None

    assignee = None
    if issue.assignee_provider_user_id:
        employee_id = resolve_author_employee_id(
            db,
            tenant_id,
            "jira",
            issue.assignee_provider_user_id,
            email_hint=issue.assignee_email,
            quarantine_event_type="jira_issue",
            quarantine_payload={"issue_key": issue.issue_key},
        )
        assignee = CanonicalPersonRef(
            employee_id=employee_id,
            provider="jira",
            provider_user_id=issue.assignee_provider_user_id,
            display_name=issue.assignee_email or issue.assignee_provider_user_id,
        )

    component_ref = None
    if issue.component_id and issue.component_id in components_by_id:
        comp = components_by_id[issue.component_id]
        component_ref = CanonicalComponentRef(
            component_id=issue.component_id,
            name=getattr(comp, "name", ""),
        )

    return CanonicalWorkItem(
        source="jira",
        work_item_id=issue.issue_key,
        issue_type=issue.issue_type,
        priority=issue.priority,
        status=issue.status,
        project_key=issue.project_key,
        summary=(issue.summary or issue.issue_key).strip(),
        assignee=assignee,
        component=component_ref,
        properties={"priority": issue.priority, "status": issue.status},
    )
