from datetime import datetime

from sqlalchemy.orm import Session

from app.models.operational import (
    Assignment,
    DoaFileSnapshot,
    Employee,
    GitHubOwnershipSnapshot,
    NotionDocSnapshot,
    RoleHistory,
    FileRiskSnapshot,
)
from app.models.tenant import Tenant
from app.schemas.org import EmployeeSchema
from app.schemas.role_evolution import (
    EmployeeDeleteResponse,
    EmployeeUpdateRequest,
    EmployeeUpdateResponse,
    RoleHistoryRecord,
)
from app.services.cognee_ingest import ingest_org_chart_to_cognee
from app.services.org_chart_read import load_org_chart
from app.services.org_helpers import would_create_cycle
from app.services.role_utils import is_leadership_role


def _build_role_evolution_narrative(
    employee: Employee,
    old_role: str,
    new_role: str,
    direct_report_count: int,
) -> str:
    lines = [
        f"Role evolution event: {employee.name} ({employee.email}) "
        f"transitioned from '{old_role}' to '{new_role}'."
    ]

    became_manager = is_leadership_role(new_role) and not is_leadership_role(old_role)
    left_management = is_leadership_role(old_role) and not is_leadership_role(new_role)

    if became_manager and direct_report_count > 0:
        lines.append(
            f"{employee.name} was promoted into a managerial scope with "
            f"{direct_report_count} direct report(s). Prior individual-contributor "
            "graph constraints are replaced by manages and directReportOf edges."
        )
    elif direct_report_count > 0 and is_leadership_role(new_role):
        lines.append(
            f"{employee.name} maintains managerial scope over "
            f"{direct_report_count} direct report(s) under title '{new_role}'."
        )
    elif left_management:
        lines.append(
            f"{employee.name} returned to an individual contributor trajectory; "
            "prior managerial edge typing is superseded in the knowledge graph."
        )

    return "\n".join(lines)


def _apply_assignments_update(
    db: Session,
    employee_id: str,
    tenant_id,
    assignments_update,
) -> None:
    if assignments_update is None:
        return

    db.query(Assignment).filter(
        Assignment.employee_id == employee_id,
        Assignment.tenant_id == tenant_id,
    ).delete()

    for component_id in assignments_update.component_ids:
        if not component_id:
            continue
        db.add(
            Assignment(
                tenant_id=tenant_id,
                employee_id=employee_id,
                component_id=component_id,
                codebase_share_pct=0.0,
            )
        )


async def update_employee_with_role_evolution(
    db: Session,
    employee_id: str,
    payload: EmployeeUpdateRequest,
    tenant: Tenant,
) -> EmployeeUpdateResponse:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .one_or_none()
    )
    if not employee:
        raise ValueError(f"Employee '{employee_id}' not found.")

    was_active = employee.active
    old_role = employee.role
    role_changed = payload.role is not None and payload.role.strip() != old_role

    if payload.name is not None:
        employee.name = payload.name.strip()
    if payload.role is not None:
        employee.role = payload.role.strip()
    if payload.email is not None:
        employee.email = str(payload.email)
    if payload.tenure_years is not None:
        employee.tenure_years = payload.tenure_years
    if payload.active is not None:
        employee.active = payload.active
    if "team_name" in payload.model_fields_set:
        employee.team_name = payload.team_name.strip() if payload.team_name else None

    if "manager_id" in payload.model_fields_set:
        manager_id = payload.manager_id if payload.manager_id else None
        if manager_id and manager_id != employee_id:
            org_preview = load_org_chart(db, tenant)
            preview_employees = [
                EmployeeSchema(
                    id=item.id,
                    name=item.name,
                    role=item.role,
                    email=item.email,
                    tenure_years=item.tenure_years,
                    manager_id=item.manager_id if item.id != employee_id else manager_id,
                    team_name=item.team_name,
                )
                for item in org_preview.employees
            ]
            if would_create_cycle(preview_employees, employee_id, manager_id):
                raise ValueError("Cyclical reporting line detected for manager assignment.")
        employee.manager_id = manager_id

    history_entry: RoleHistoryRecord | None = None
    if role_changed:
        record = RoleHistory(
            tenant_id=tenant.id,
            employee_id=employee_id,
            old_role=old_role,
            new_role=employee.role,
            changed_at=datetime.utcnow(),
        )
        db.add(record)
        db.flush()
        history_entry = RoleHistoryRecord(
            id=record.id,
            employee_id=record.employee_id,
            old_role=record.old_role,
            new_role=record.new_role,
            changed_at=record.changed_at,
        )

    if payload.assignments is not None:
        _apply_assignments_update(db, employee_id, tenant.id, payload.assignments)

    if was_active and "active" in payload.model_fields_set and payload.active is False:
        from app.services.github_orphans import snapshot_departure_orphan_baseline

        snapshot_departure_orphan_baseline(db, tenant.id, employee_id)

    db.commit()

    direct_report_count = (
        db.query(Employee)
        .filter(Employee.manager_id == employee_id, Employee.tenant_id == tenant.id)
        .count()
    )

    org = load_org_chart(db, tenant)
    supplemental = _build_role_evolution_narrative(
        employee,
        old_role,
        employee.role,
        direct_report_count,
    )

    cognee_result = await ingest_org_chart_to_cognee(
        org,
        tenant_id=tenant.id,
        custom_prompt=(
            "Dynamic role evolution: update organizational graph predicates when "
            "employees transition between individual contributor and managerial roles. "
            "Maintain reportsTo, directReportOf, manages, and ownsComponent relationships."
        ),
        supplemental_narrative=supplemental,
    )

    return EmployeeUpdateResponse(
        employee_id=employee_id,
        role_changed=role_changed,
        role_history_entry=history_entry,
        cognee_dataset=str(cognee_result["cognee_dataset"]),
        graph_nodes_created=int(cognee_result["graph_nodes_created"]),
        graph_edges_created=int(cognee_result["graph_edges_created"]),
    )


async def delete_employee_with_cognee_sync(
    db: Session,
    employee_id: str,
    tenant: Tenant,
) -> EmployeeDeleteResponse:
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.tenant_id == tenant.id)
        .one_or_none()
    )
    if not employee:
        raise ValueError(f"Employee '{employee_id}' not found.")

    employee_name = employee.name
    new_manager_id = employee.manager_id

    direct_reports_reparented = (
        db.query(Employee)
        .filter(Employee.manager_id == employee_id, Employee.tenant_id == tenant.id)
        .update(
            {Employee.manager_id: new_manager_id},
            synchronize_session=False,
        )
    )

    db.query(GitHubOwnershipSnapshot).filter(
        GitHubOwnershipSnapshot.employee_id == employee_id,
        GitHubOwnershipSnapshot.tenant_id == tenant.id,
    ).delete(synchronize_session=False)

    db.query(DoaFileSnapshot).filter(
        DoaFileSnapshot.employee_id == employee_id,
        DoaFileSnapshot.tenant_id == tenant.id,
    ).delete(synchronize_session=False)

    db.query(FileRiskSnapshot).filter(
        FileRiskSnapshot.primary_owner_employee_id == employee_id,
        FileRiskSnapshot.tenant_id == tenant.id,
    ).update(
        {
            FileRiskSnapshot.primary_owner_employee_id: None,
            FileRiskSnapshot.primary_owner_doa_pct: None,
        },
        synchronize_session=False,
    )

    db.query(NotionDocSnapshot).filter(
        NotionDocSnapshot.owner_employee_id == employee_id,
        NotionDocSnapshot.tenant_id == tenant.id,
    ).update(
        {NotionDocSnapshot.owner_employee_id: None},
        synchronize_session=False,
    )

    db.delete(employee)
    db.commit()

    org = load_org_chart(db, tenant)
    supplemental = (
        f"Org chart removal: {employee_name} ({employee_id}) was removed from "
        f"the organization. {direct_reports_reparented} direct report(s) were "
        "re-parented to the removed employee's manager."
    )
    cognee_result = await ingest_org_chart_to_cognee(
        org,
        tenant_id=tenant.id,
        custom_prompt=(
            "Org chart update: remove deleted employees and refresh reporting "
            "lines, manages, and ownsComponent relationships."
        ),
        supplemental_narrative=supplemental,
    )

    return EmployeeDeleteResponse(
        employee_id=employee_id,
        direct_reports_reparented=direct_reports_reparented,
        cognee_dataset=str(cognee_result["cognee_dataset"]),
        graph_nodes_created=int(cognee_result["graph_nodes_created"]),
        graph_edges_created=int(cognee_result["graph_edges_created"]),
    )


def list_role_history(
    db: Session, employee_id: str, tenant: Tenant
) -> list[RoleHistoryRecord]:
    return [
        RoleHistoryRecord(
            id=record.id,
            employee_id=record.employee_id,
            old_role=record.old_role,
            new_role=record.new_role,
            changed_at=record.changed_at,
        )
        for record in db.query(RoleHistory)
        .filter(
            RoleHistory.employee_id == employee_id,
            RoleHistory.tenant_id == tenant.id,
        )
        .order_by(RoleHistory.changed_at.desc())
        .all()
    ]


def list_active_roles(db: Session, tenant: Tenant) -> list[str]:
    roles = (
        db.query(Employee.role)
        .filter(Employee.tenant_id == tenant.id)
        .distinct()
        .all()
    )
    return sorted({role for (role,) in roles if role})
