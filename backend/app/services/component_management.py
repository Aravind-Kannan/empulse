"""Update, delete, dedupe, and auto-assign org-chart components."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.operational import Assignment, Component, Employee, GitHubOwnershipSnapshot
from app.models.tenant import Tenant
from app.services.cognee_ingest import ingest_org_chart_to_cognee
from app.services.employee_ids import scope_component_id, tenant_prefix
from app.services.org_chart_read import load_org_chart

logger = logging.getLogger(__name__)

AUTO_DESC_PREFIX = "AUTO:"
VALID_CRITICALITIES = frozenset({"tier1_revenue", "tier2_core", "tier3_support"})


def _tenant_scoped_prefix(tenant_id: uuid.UUID) -> str:
    return f"comp-{tenant_prefix(tenant_id)}-"


def consolidate_duplicate_components(db: Session, tenant_id: uuid.UUID) -> int:
    """Merge unscoped duplicate components into tenant-scoped rows."""
    scoped_prefix = _tenant_scoped_prefix(tenant_id)
    rows = db.query(Component).filter(Component.tenant_id == tenant_id).all()
    by_name: dict[str, list[Component]] = defaultdict(list)
    for row in rows:
        by_name[row.name].append(row)

    removed = 0
    for group in by_name.values():
        if len(group) < 2:
            continue
        scoped = [row for row in group if row.id.startswith(scoped_prefix)]
        unscoped = [row for row in group if not row.id.startswith(scoped_prefix)]
        if not scoped or not unscoped:
            continue
        keeper = scoped[0]
        for duplicate in unscoped:
            db.query(Assignment).filter(
                Assignment.tenant_id == tenant_id,
                Assignment.component_id == duplicate.id,
            ).update(
                {Assignment.component_id: keeper.id},
                synchronize_session=False,
            )
            db.query(GitHubOwnershipSnapshot).filter(
                GitHubOwnershipSnapshot.tenant_id == tenant_id,
                GitHubOwnershipSnapshot.component_id == duplicate.id,
            ).update(
                {GitHubOwnershipSnapshot.component_id: keeper.id},
                synchronize_session=False,
            )
            db.delete(duplicate)
            removed += 1

    if removed:
        _rewrite_integration_component_maps(db, tenant_id)
        db.commit()
    return removed


def _rewrite_integration_component_maps(db: Session, tenant_id: uuid.UUID) -> None:
    from app.services.integration_config_store import (
        get_github_config,
        get_jira_config,
        save_github_config,
        save_jira_config,
    )

    scoped_prefix = _tenant_scoped_prefix(tenant_id)
    valid_ids = {
        row.id
        for row in db.query(Component.id).filter(Component.tenant_id == tenant_id).all()
    }

    def remap(component_id: str) -> str:
        if component_id in valid_ids:
            return component_id
        scoped = scope_component_id(component_id, tenant_id)
        return scoped if scoped in valid_ids else component_id

    github_config = get_github_config(db, tenant_id)
    if github_config:
        path_map = {
            prefix: remap(component_id)
            for prefix, component_id in (github_config.path_component_map or {}).items()
        }
        default_id = (
            remap(github_config.default_component_id)
            if github_config.default_component_id
            else None
        )
        save_github_config(
            db,
            tenant_id,
            github_config.model_copy(
                update={
                    "path_component_map": path_map,
                    "default_component_id": default_id,
                }
            ),
        )

    jira_config = get_jira_config(db, tenant_id)
    if jira_config:
        field_map = {
            name: remap(component_id)
            for name, component_id in (jira_config.component_field_map or {}).items()
        }
        project_map = {
            project: remap(component_id)
            for project, component_id in (jira_config.project_component_map or {}).items()
        }
        default_id = (
            remap(jira_config.default_component_id)
            if jira_config.default_component_id
            else None
        )
        save_jira_config(
            db,
            tenant_id,
            jira_config.model_copy(
                update={
                    "component_field_map": field_map,
                    "project_component_map": project_map,
                    "default_component_id": default_id,
                }
            ),
        )


def sync_assignments_from_github_ownership(db: Session, tenant_id: uuid.UUID) -> int:
    """Create org-chart assignments from GitHub ownership when unassigned."""
    assigned_components = {
        row[0]
        for row in db.query(Assignment.component_id)
        .filter(Assignment.tenant_id == tenant_id)
        .distinct()
        .all()
    }
    created = 0
    snapshots = (
        db.query(GitHubOwnershipSnapshot)
        .filter(GitHubOwnershipSnapshot.tenant_id == tenant_id)
        .all()
    )
    best_by_component: dict[str, tuple[str, float]] = {}
    for snapshot in snapshots:
        if snapshot.component_id in assigned_components:
            continue
        current = best_by_component.get(snapshot.component_id)
        if current is None or snapshot.ownership_pct > current[1]:
            best_by_component[snapshot.component_id] = (
                snapshot.employee_id,
                snapshot.ownership_pct,
            )

    for component_id, (employee_id, ownership_pct) in best_by_component.items():
        existing = (
            db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.component_id == component_id,
                Assignment.employee_id == employee_id,
            )
            .first()
        )
        if existing:
            continue
        db.add(
            Assignment(
                tenant_id=tenant_id,
                employee_id=employee_id,
                component_id=component_id,
                codebase_share_pct=round(ownership_pct, 2),
            )
        )
        assigned_components.add(component_id)
        created += 1

    if created:
        db.commit()
    return created


async def update_component_with_cognee_sync(
    db: Session,
    component_id: str,
    *,
    tenant: Tenant,
    name: str | None = None,
    tags: str | None = None,
    criticality: str | None = None,
    description: str | None = None,
) -> dict[str, object]:
    row = (
        db.query(Component)
        .filter(Component.id == component_id, Component.tenant_id == tenant.id)
        .one_or_none()
    )
    if row is None:
        raise ValueError(f"Component '{component_id}' not found.")

    if name is not None:
        row.name = name.strip()
    if tags is not None:
        row.tags = _normalize_tags(tags)
    if criticality is not None:
        cleaned = criticality.strip()
        if cleaned not in VALID_CRITICALITIES:
            raise ValueError(f"Invalid criticality '{criticality}'.")
        row.criticality = cleaned
    if description is not None:
        row.description = description.strip()

    db.commit()
    org = load_org_chart(db, tenant)
    cognee_result = await ingest_org_chart_to_cognee(
        org,
        tenant_id=tenant.id,
        custom_prompt=(
            "Update component metadata in the organizational graph including "
            "component names, tags, criticality tiers, and ownsComponent edges."
        ),
        supplemental_narrative=f"Component '{row.name}' metadata updated.",
    )
    return {
        "component_id": row.id,
        "cognee_dataset": cognee_result["cognee_dataset"],
        "graph_nodes_created": cognee_result["graph_nodes_created"],
        "graph_edges_created": cognee_result["graph_edges_created"],
    }


async def delete_component_with_cognee_sync(
    db: Session,
    component_id: str,
    *,
    tenant: Tenant,
) -> dict[str, object]:
    from app.services.cognee_ingest import _delete_component_dependents

    row = (
        db.query(Component)
        .filter(Component.id == component_id, Component.tenant_id == tenant.id)
        .one_or_none()
    )
    if row is None:
        raise ValueError(f"Component '{component_id}' not found.")

    _delete_component_dependents(db, tenant.id, component_id)
    db.delete(row)
    db.commit()

    org = load_org_chart(db, tenant)
    cognee_result = await ingest_org_chart_to_cognee(
        org,
        tenant_id=tenant.id,
        custom_prompt=(
            "Remove deleted component nodes and ownsComponent relationships "
            "from the organizational graph."
        ),
        supplemental_narrative=f"Component '{row.name}' removed from org chart.",
    )
    return {
        "component_id": component_id,
        "cognee_dataset": cognee_result["cognee_dataset"],
        "graph_nodes_created": cognee_result["graph_nodes_created"],
        "graph_edges_created": cognee_result["graph_edges_created"],
    }


def _normalize_tags(raw: str) -> str:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return ", ".join(dict.fromkeys(parts))


async def finalize_org_after_integration_sync(
    db: Session,
    tenant: Tenant,
) -> dict[str, int]:
    """Dedupe components, infer assignments, and sync org chart into Cognee."""
    removed = consolidate_duplicate_components(db, tenant_id=tenant.id)
    assignments_created = sync_assignments_from_github_ownership(db, tenant.id)
    org = load_org_chart(db, tenant)
    cognee_result = await ingest_org_chart_to_cognee(
        org,
        tenant_id=tenant.id,
        custom_prompt=(
            "Synchronize organizational graph after integration sync including "
            "employees, components, assignments, and ownsComponent relationships."
        ),
        supplemental_narrative=(
            "Integration sync completed; org chart components and assignments refreshed."
        ),
    )
    return {
        "duplicates_removed": removed,
        "assignments_created": assignments_created,
        "graph_nodes_created": int(cognee_result["graph_nodes_created"]),
        "graph_edges_created": int(cognee_result["graph_edges_created"]),
    }


def scoped_component_id(tenant_id: uuid.UUID, *parts: str, prefix: str = "comp") -> str:
    from app.services.component_provisioning import _component_id

    return scope_component_id(_component_id(prefix, *parts), tenant_id)
