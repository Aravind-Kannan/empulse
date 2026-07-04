"""Deliver exit handover markdown to an employee's Slack DM."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.operational import Employee, EmployeeIdentity
from app.schemas.exit import HandoverSlackSendResponse
from app.services.exit_handover import build_handover_markdown
from app.services.integration_config_store import get_slack_config
from app.services.slack_client import (
    lookup_slack_user_by_email,
    open_dm_channel,
    upload_markdown_to_channel,
)


def _resolve_slack_user_id(
    db: Session,
    tenant_id: uuid.UUID,
    employee: Employee,
    *,
    bot_token: str,
) -> str:
    row = (
        db.query(EmployeeIdentity.provider_username_or_id)
        .filter(
            EmployeeIdentity.tenant_id == tenant_id,
            EmployeeIdentity.employee_id == employee.id,
            EmployeeIdentity.provider == "slack",
        )
        .first()
    )
    if row and row[0]:
        return str(row[0])

    if employee.email:
        resolved = lookup_slack_user_by_email(bot_token, employee.email)
        if resolved:
            return resolved

    raise ValueError(
        f"No Slack user mapping for {employee.name}. Link their Slack identity "
        "under Settings → Identity mapping, or ensure users:read.email is enabled "
        "and their Empulse email matches Slack."
    )


async def send_handover_slack_dm(
    db: Session,
    tenant,
    employee_id: str,
    *,
    prefill_era: bool = False,
    markdown: str | None = None,
    filename: str | None = None,
) -> HandoverSlackSendResponse:
    config = get_slack_config(db, tenant.id)
    if config is None or not config.bot_token.strip():
        raise ValueError(
            "Slack is not connected for this tenant. Configure Slack under Settings → Integrations."
        )

    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .first()
    )
    if employee is None:
        raise ValueError(f"Employee '{employee_id}' not found.")

    if markdown and markdown.strip():
        handover_employee_id = employee.id
        handover_employee_name = employee.name
        handover_markdown = markdown.strip()
        safe_name = employee.name.lower().replace(" ", "-")
        handover_filename = filename or f"handover-{safe_name}.md"
    else:
        handover = await build_handover_markdown(
            db,
            employee_id,
            tenant,
            prefill_era=prefill_era,
        )
        handover_employee_id = handover.employee_id
        handover_employee_name = handover.employee_name
        handover_markdown = handover.markdown_content or handover.markdown
        handover_filename = (
            handover.filename if handover.filename.endswith(".md") else f"{handover.filename}.md"
        )

    if not handover_filename.endswith(".md"):
        handover_filename = f"{handover_filename}.md"

    slack_user_id = _resolve_slack_user_id(
        db,
        tenant.id,
        employee,
        bot_token=config.bot_token,
    )
    channel_id = open_dm_channel(config.bot_token, slack_user_id)
    initial_comment = (
        f"Empulse handover blueprint for *{handover_employee_name}* is attached. "
        "Generated from ownership, Jira, Slack, and documentation signals."
    )
    file_id = upload_markdown_to_channel(
        config.bot_token,
        channel_id=channel_id,
        filename=handover_filename,
        content=handover_markdown,
        title=f"Handover — {handover_employee_name}",
        initial_comment=initial_comment,
    )

    return HandoverSlackSendResponse(
        employee_id=handover_employee_id,
        employee_name=handover_employee_name,
        slack_user_id=slack_user_id,
        channel_id=channel_id,
        filename=handover_filename,
        file_id=file_id or None,
        message=f"Handover sent to {employee.name} via Slack DM.",
    )
