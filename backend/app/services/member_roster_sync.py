from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.operational import Employee
from app.models.tenant import Tenant
from app.schemas.employee_master import (
    EmployeeMasterDataResponse,
    FetchUsersRequest,
)
from app.schemas.org import EmployeeSchema, OrgChartIngestRequest
from app.services.cognee_ingest import ingest_org_chart_to_cognee, persist_org_chart
from app.services.employee_master_fetch import (
    enrich_jira_credentials_from_db,
    fetch_employee_master_data,
)
from app.services.org_chart_read import load_org_chart


def _load_org_for_merge(db: Session, tenant: Tenant) -> OrgChartIngestRequest:
    """Load tenant org chart, or an empty roster when none has been persisted yet."""
    has_employees = (
        db.query(Employee.id)
        .filter(Employee.tenant_id == tenant.id)
        .limit(1)
        .first()
        is not None
    )
    if not has_employees:
        return OrgChartIngestRequest(company=tenant.company_name, employees=[])
    return load_org_chart(db, tenant)


def merge_master_data_into_org(
    current: OrgChartIngestRequest,
    master: EmployeeMasterDataResponse,
) -> tuple[OrgChartIngestRequest, int, int]:
    """Merge imported members into the existing roster by email (additive)."""
    existing_by_email = {employee.email.lower(): employee for employee in current.employees}
    merged_employees = list(current.employees)
    added = 0
    updated = 0

    for imported in master.employees:
        email_key = str(imported.email).lower()
        existing = existing_by_email.get(email_key)
        if existing:
            changes = (
                existing.name != imported.name
                or existing.role != imported.role
                or existing.manager_id != imported.manager_id
                or existing.tenure_years != imported.tenure_years
            )
            if changes:
                updated += 1
            replacement = existing.model_copy(
                update={
                    "name": imported.name,
                    "role": imported.role,
                    "manager_id": imported.manager_id or existing.manager_id,
                    "tenure_years": imported.tenure_years or existing.tenure_years,
                }
            )
            merged_employees = [
                replacement if employee.id == existing.id else employee
                for employee in merged_employees
            ]
            existing_by_email[email_key] = replacement
            continue

        added += 1
        created = EmployeeSchema(
            id=imported.id,
            name=imported.name,
            role=imported.role,
            email=imported.email,
            tenure_years=imported.tenure_years,
            manager_id=imported.manager_id,
        )
        merged_employees.append(created)
        existing_by_email[email_key] = created

    merged = OrgChartIngestRequest(
        company=current.company or master.company,
        employees=merged_employees,
        components=current.components,
        assignments=current.assignments,
    )
    return merged, added, updated


def _master_from_empty_org(
    master: EmployeeMasterDataResponse,
) -> OrgChartIngestRequest:
    return OrgChartIngestRequest(
        company=master.company,
        employees=[
            EmployeeSchema(
                id=employee.id,
                name=employee.name,
                role=employee.role,
                email=employee.email,
                tenure_years=employee.tenure_years,
                manager_id=employee.manager_id,
            )
            for employee in master.employees
        ],
    )


async def sync_member_roster(
    db: Session,
    tenant: Tenant,
    credentials: FetchUsersRequest,
    *,
    replace_existing: bool = False,
) -> dict[str, int | str | list[str]]:
    credentials = enrich_jira_credentials_from_db(credentials, db, tenant.id)
    master = fetch_employee_master_data(
        credentials.sources,
        company=credentials.company or tenant.company_name,
        credentials=credentials,
        flat_hierarchy=credentials.flat_hierarchy,
        tenant_id=tenant.id,
        skip_failed_sources=True,
    )

    current = _load_org_for_merge(db, tenant)
    if replace_existing or not current.employees:
        merged = _master_from_empty_org(master)
        added = len(merged.employees)
        updated = 0
    else:
        merged, added, updated = merge_master_data_into_org(current, master)

    scoped_payload = persist_org_chart(db, merged, tenant.id)
    cognee_result = await ingest_org_chart_to_cognee(
        scoped_payload,
        tenant_id=tenant.id,
        custom_prompt=(
            "Sync member roster from connected integrations. "
            "Preserve reporting relationships and team metadata."
        ),
        supplemental_narrative=(
            f"Member roster sync from {', '.join(master.sources_queried)}. "
            f"{added} added, {updated} updated."
        ),
    )

    return {
        "sources": master.sources_queried,
        "employees_imported": len(master.employees),
        "employees_added": added,
        "employees_updated": updated,
        "employees_persisted": len(merged.employees),
        "hierarchy_mode": master.hierarchy_mode,
        "cognee_dataset": str(cognee_result["cognee_dataset"]),
        "graph_nodes_created": int(cognee_result["graph_nodes_created"]),
        "graph_edges_created": int(cognee_result["graph_edges_created"]),
        "source_errors": master.source_errors,
    }
