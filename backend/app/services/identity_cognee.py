"""Push confirmed employee ↔ provider identity mappings into the tenant Cognee graph."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.services.cognee_ingest import (
    PROVIDER_IDENTITY_FIELDS,
    GraphEmployee,
    build_tenant_org_graph_nodes,
)
from app.services.tenant_cognee import tenant_add_and_cognify, tenant_add_data_points
from app.tenancy import tenant_dataset_name

logger = logging.getLogger(__name__)


def _identity_narrative(node: GraphEmployee) -> str:
    links: list[str] = []
    for provider, field in PROVIDER_IDENTITY_FIELDS.items():
        value = getattr(node, field, "")
        if value:
            links.append(f"{provider}={value}")
    identity_text = ", ".join(links) if links else "no provider ids"
    return (
        f"Identity mapping: {node.name} ({node.email}, employee {node.external_id}) "
        f"is confirmed on {identity_text}."
    )


async def sync_employee_identities_to_cognee(
    db: Session,
    tenant_id: uuid.UUID,
    employee_ids: set[str],
) -> dict[str, int | str]:
    """Upsert one GraphEmployee per saved mapping with provider ids and org anchor edges."""
    if not employee_ids:
        return {"synced": 0}

    employee_nodes, component_nodes, _ = build_tenant_org_graph_nodes(db, tenant_id)
    if not employee_nodes:
        return {"synced": 0, "reason": "no_org_graph"}

    data_points: list[GraphEmployee] = []
    narrative_lines: list[str] = []
    for employee_id in sorted(employee_ids):
        node = employee_nodes.get(employee_id)
        if node is None:
            continue
        data_points.append(node)
        narrative_lines.append(_identity_narrative(node))

    if not data_points:
        return {"synced": 0, "reason": "employees_not_found"}

    try:
        await tenant_add_data_points(
            tenant_id,
            data_points,
            employee_nodes=employee_nodes,
            component_nodes=component_nodes,
        )
        if narrative_lines:
            await tenant_add_and_cognify(
                "\n".join(narrative_lines),
                tenant_id,
                custom_prompt=(
                    "Record confirmed engineering identity mappings linking canonical "
                    "employees to GitHub, Jira, Slack, and Notion provider user IDs."
                ),
            )
    except Exception as exc:
        logger.warning(
            "Cognee identity sync failed for tenant %s employees %s: %s",
            tenant_id,
            sorted(employee_ids),
            exc,
        )
        return {"synced": 0, "error": str(exc)}

    return {
        "synced": len(data_points),
        "cognee_dataset": tenant_dataset_name(tenant_id),
    }
